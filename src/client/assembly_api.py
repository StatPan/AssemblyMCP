import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

# Configure logging
logger = logging.getLogger(__name__)


class AssemblyAPIError(Exception):
    """Custom exception for Assembly API errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _is_retryable_error(exception):
    """Check if the exception is retryable."""
    if isinstance(exception, (httpx.NetworkError, httpx.TimeoutException)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in [429, 500, 502, 503, 504]
    return False


class AssemblyAPIClient:
    """Client for Korean National Assembly Open API."""

    BASE_URL = "https://open.assembly.go.kr/portal/openapi"

    def __init__(self, api_key: str = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("ASSEMBLY_API_KEY")

        if not self.api_key:
            raise ValueError("ASSEMBLY_API_KEY is not set.")

        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30.0, follow_redirects=True)
        self.specs: dict[str, dict[str, Any]] = {}
        self._load_specs()

    def _load_specs(self):
        """Load API specifications from specs/ directory."""
        try:
            current_file = Path(__file__)
            # Go up to project root (src/client/assembly_api.py -> src/client -> src -> root)
            project_root = current_file.parent.parent.parent
            specs_dir = project_root / "specs"

            if not specs_dir.exists():
                logger.warning(f"Specs directory not found at {specs_dir}")
                return

            for spec_file in specs_dir.glob("all_apis_p*.json"):
                try:
                    with open(spec_file, encoding="utf-8") as f:
                        data = json.load(f)
                        if "OPENSRVAPI" in data:
                            for item in data["OPENSRVAPI"]:
                                if "row" in item:
                                    for row in item["row"]:
                                        inf_id = row.get("INF_ID")
                                        if inf_id:
                                            self.specs[inf_id] = row
                except Exception as e:
                    logger.error(f"Failed to load spec file {spec_file}: {e}")

            logger.info(f"Loaded {len(self.specs)} API specs.")

        except Exception as e:
            logger.error(f"Error loading specs: {e}")

    def validate_service_id(self, service_id: str) -> bool:
        """Check if service_id exists in loaded specs."""
        return service_id in self.specs

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable_error),
    )
    async def get_data(
        self, service_id: str, params: dict[str, Any] = None, fmt: str = "json"
    ) -> dict[str, Any] | str:
        """
        Fetch data from the API.

        Args:
            service_id: The API service ID.
            params: Query parameters.
            fmt: Response format ('json' or 'xml').

        Returns:
            Parsed JSON dict or raw XML string.
        """
        if not self.validate_service_id(service_id):
            logger.warning(f"Service ID {service_id} not found in loaded specs.")

        url = f"/{service_id}"
        if fmt.lower() == "json":
            url += "/json"
        elif fmt.lower() == "xml":
            url += "/xml"

        default_params = {
            "KEY": self.api_key,
            "pIndex": 1,
            "pSize": 100,
        }
        merged_params = {**default_params, **(params or {})}

        try:
            response = await self.client.get(url, params=merged_params)
            response.raise_for_status()

            if fmt.lower() == "json":
                data = response.json()
                self._check_api_error(data, service_id)
                return data
            else:
                return response.text

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise

    def _check_api_error(self, data: dict[str, Any], service_id: str):
        """Check for API specific error codes."""
        # Expected structure: { service_id: [ { "head": [ ... { "RESULT": ... } ] }, ... ] }
        if service_id in data:
            items = data[service_id]
            for item in items:
                if "head" in item:
                    for head_item in item["head"]:
                        if "RESULT" in head_item:
                            result = head_item["RESULT"]
                            code = result.get("CODE")
                            message = result.get("MESSAGE")

                            # Check for specific error codes
                            # 290, 300, 337 are mentioned in requirements
                            if code in ["INFO-200", "INFO-290", "INFO-300", "INFO-337"]:
                                # These might be "No Data" or similar info codes
                                logger.warning(f"API Result: {code} - {message}")

                                # INFO-200 usually means "No Data"
                                if code == "INFO-200":
                                    return  # No data is valid result

                                raise AssemblyAPIError(code, message)
