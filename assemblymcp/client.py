import json
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .spec_parser import APISpec, SpecParseError, SpecParser

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

    def __init__(self, api_key: str = None, spec_cache_dir: Path | None = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("ASSEMBLY_API_KEY")

        if not self.api_key:
            raise ValueError("ASSEMBLY_API_KEY is not set.")

        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.specs: dict[str, dict[str, Any]] = {}

        # Default to user cache directory if not provided
        if spec_cache_dir is None:
            # Use ~/.cache/assemblymcp/specs
            spec_cache_dir = Path.home() / ".cache" / "assemblymcp" / "specs"
            spec_cache_dir.mkdir(parents=True, exist_ok=True)

        self.spec_parser = SpecParser(cache_dir=spec_cache_dir)
        self.parsed_specs: dict[str, APISpec] = {}
        self._load_specs()

    def _load_specs(self):
        """Load API specifications from specs/ directory."""
        try:
            current_file = Path(__file__)
            specs_dir = current_file.parent / "specs"

            if not specs_dir.exists():
                logger.warning(f"Specs directory not found at {specs_dir}")
                return

            # 1. Load Master List (all_apis.json)
            master_file = specs_dir / "all_apis.json"
            if master_file.exists():
                try:
                    with open(master_file, encoding="utf-8") as f:
                        data = json.load(f)
                        if "OPENSRVAPI" in data:
                            for item in data["OPENSRVAPI"]:
                                if "row" in item:
                                    for row in item["row"]:
                                        inf_id = row.get("INF_ID")
                                        if inf_id:
                                            self.specs[inf_id] = row
                except Exception as e:
                    logger.error(f"Failed to load master list {master_file}: {e}")

            # 2. Load Parsed Specs from cache if available
            # We don't pre-load everything, just what's in memory or needed.
            # But we can scan the cache to populate self.parsed_specs if we wanted to,
            # for now let's just rely on lazy loading via get_endpoint.

            logger.info(f"Loaded {len(self.specs)} API definitions.")

        except Exception as e:
            logger.error(f"Error loading specs: {e}")

    def validate_service_id(self, service_id: str) -> bool:
        """Check if service_id exists in loaded specs."""
        return service_id in self.specs

    async def get_endpoint(self, service_id: str) -> str:
        """
        Get the actual API endpoint for a service ID.

        Args:
            service_id: The service ID

        Returns:
            The endpoint string

        Raises:
            SpecParseError: If spec parsing fails
        """
        if service_id not in self.parsed_specs:
            logger.info(f"Parsing spec for {service_id}")

            # Determine inf_seq from specs if available
            inf_seq = 2
            if service_id in self.specs:
                ddc_url = self.specs[service_id].get("DDC_URL", "")
                if ddc_url:
                    try:
                        parsed = urllib.parse.urlparse(ddc_url)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "infSeq" in qs:
                            inf_seq = int(qs["infSeq"][0])
                    except Exception:
                        pass  # Fallback to default 2

            spec = await self.spec_parser.parse_spec(service_id, inf_seq=inf_seq)
            self.parsed_specs[service_id] = spec

        return self.parsed_specs[service_id].endpoint

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable_error),
    )
    async def get_data(
        self, service_id: str, params: dict[str, Any] = None, fmt: str = "json"
    ) -> dict[str, Any] | str:
        """
        Fetch data from the API using dynamic endpoint resolution.

        Args:
            service_id: The API service ID (e.g., 'OK7XM1000938DS17215').
            params: Query parameters.
            fmt: Response format ('json' or 'xml').

        Returns:
            Parsed JSON dict or raw XML string.

        Raises:
            SpecParseError: If endpoint resolution fails
            AssemblyAPIError: If API returns an error
        """
        if not self.validate_service_id(service_id):
            logger.warning(f"Service ID {service_id} not found in loaded specs.")

        # Get actual endpoint from Excel spec
        try:
            endpoint = await self.get_endpoint(service_id)
        except SpecParseError as e:
            logger.error(f"Failed to get endpoint for {service_id}: {e}")
            raise

        # Build URL with actual endpoint
        url = f"{self.BASE_URL}/{endpoint}"

        # Add format parameter using Type param (not URL path)
        default_params = {
            "KEY": self.api_key,
            "Type": fmt.lower(),
            "pIndex": 1,
            "pSize": 100,
        }
        merged_params = {**default_params, **(params or {})}

        try:
            response = await self.client.get(url, params=merged_params)
            response.raise_for_status()

            if fmt.lower() == "json":
                data = response.json()
                self._check_api_error(data, endpoint)
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
