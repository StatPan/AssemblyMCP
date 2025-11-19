"""Parser for Korean National Assembly API Excel specifications."""

import asyncio
import hashlib
import json
import logging
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import openpyxl

logger = logging.getLogger(__name__)


@dataclass
class APIParameter:
    """Represents a single API parameter."""

    name: str
    type: str
    required: bool
    description: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "APIParameter":
        return cls(**data)


@dataclass
class APISpec:
    """Represents a parsed API specification."""

    service_id: str
    endpoint: str
    endpoint_url: str
    basic_params: list[APIParameter]
    request_params: list[APIParameter]

    def to_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "endpoint": self.endpoint,
            "endpoint_url": self.endpoint_url,
            "basic_params": [p.to_dict() for p in self.basic_params],
            "request_params": [p.to_dict() for p in self.request_params],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "APISpec":
        return cls(
            service_id=data["service_id"],
            endpoint=data["endpoint"],
            endpoint_url=data["endpoint_url"],
            basic_params=[APIParameter.from_dict(p) for p in data["basic_params"]],
            request_params=[APIParameter.from_dict(p) for p in data["request_params"]],
        )


class SpecParseError(Exception):
    """Raised when spec parsing fails."""

    pass


class SpecParser:
    """Parser for Excel API specification files."""

    def __init__(self, cache_dir: Path | None = None):
        """
        Initialize the spec parser.

        Args:
            cache_dir: Directory to cache downloaded Excel files. If None, uses system temp dir.
        """
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "assembly_specs"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def save_spec_json(self, spec: APISpec, output_dir: Path) -> Path:
        """Save APISpec to a JSON file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{spec.service_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(spec.to_dict(), f, ensure_ascii=False, indent=2)
        return output_file

    async def download_spec(self, service_id: str, inf_seq: int = 2) -> Path:
        """
        Download Excel specification file for a service.

        Args:
            service_id: The service ID (e.g., 'OK7XM1000938DS17215')
            inf_seq: The specification sequence number (default: 2)

        Returns:
            Path to the downloaded Excel file

        Raises:
            SpecParseError: If download fails
        """
        cache_file = self.cache_dir / f"{service_id}.xlsx"

        # Return cached file if exists
        if cache_file.exists():
            logger.info(f"Using cached spec for {service_id}")
            return cache_file

        # Download from DDC_URL
        url = f"https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId={service_id}&infSeq={inf_seq}"

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                if len(response.content) < 100:
                    content_preview = response.content[:50]
                    raise SpecParseError(
                        f"Downloaded file too small ({len(response.content)} bytes): "
                        f"{content_preview}"
                    )

                # Save to cache
                with open(cache_file, "wb") as f:
                    f.write(response.content)

                logger.info(f"Downloaded spec for {service_id} ({len(response.content)} bytes)")
                return cache_file

        except httpx.HTTPError as e:
            raise SpecParseError(f"Failed to download spec for {service_id}: {e}") from e

    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of the hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    async def download_if_changed(self, service_id: str, inf_seq: int = 2) -> bool:
        """
        Download spec and check if it has changed compared to cache.

        Args:
            service_id: The service ID
            inf_seq: The specification sequence number

        Returns:
            True if the file was updated (changed), False otherwise.
        """
        cache_file = self.cache_dir / f"{service_id}.xlsx"

        # Download to a temporary file first
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            url = f"https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId={service_id}&infSeq={inf_seq}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Check for correct content type before saving
                content_type = response.headers.get("Content-Type", "")
                if "spreadsheetml" not in content_type:
                    raise SpecParseError(
                        f"Unexpected content type for {service_id}: {content_type}. "
                        f"Expected Excel file."
                    )

                if len(response.content) < 100:
                    raise SpecParseError(
                        f"Downloaded file too small: {len(response.content)} bytes"
                    )

                with open(tmp_path, "wb") as f:
                    f.write(response.content)

            # Calculate hash of new file
            new_hash = self.calculate_file_hash(tmp_path)

            # If cache exists, compare hashes
            if cache_file.exists():
                old_hash = self.calculate_file_hash(cache_file)
                if new_hash == old_hash:
                    logger.info(f"Spec for {service_id} is unchanged.")
                    tmp_path.unlink()  # Delete temp file
                    return False

            # If we got here, it's either new or changed
            # Move temp file to cache (overwrite)
            # Use shutil.move to handle cross-device moves
            shutil.move(str(tmp_path), str(cache_file))
            logger.info(f"Spec for {service_id} updated.")
            return True

        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise SpecParseError(f"Failed to sync spec for {service_id}: {e}") from e

    async def parse_spec(self, service_id: str) -> APISpec:
        """
        Parse Excel specification file to extract API details.

        Args:
            service_id: The service ID to parse

        Returns:
            APISpec object containing parsed specification

        Raises:
            SpecParseError: If parsing fails
        """
        spec_file = await self.download_spec(service_id)

        def _parse_sync():
            try:
                wb = openpyxl.load_workbook(spec_file)
                ws = wb["Sheet1"]

                # Extract endpoint URL
                endpoint_url = self._extract_endpoint_url(ws)
                if not endpoint_url:
                    raise SpecParseError(f"Could not find endpoint URL in spec for {service_id}")

                endpoint = endpoint_url.split("/")[-1]

                # Extract parameters
                basic_params = []
                request_params = []

                in_basic_section = False
                in_request_section = False

                for row in ws.iter_rows(min_row=1, values_only=True):
                    if not row or not any(row):
                        continue

                    first_cell = str(row[0]) if row[0] else ""

                    # Check section markers
                    if "기본인자" in first_cell:
                        in_basic_section = True
                        in_request_section = False
                        continue
                    elif "요청인자" in first_cell:
                        in_basic_section = False
                        in_request_section = True
                        continue
                    elif "출력값" in first_cell or "출력명" in first_cell:
                        break

                    # Parse parameter rows
                    if (in_basic_section or in_request_section) and len(row) >= 3 and row[1]:
                        type_str = str(row[1])
                        if "필수" in type_str or "선택" in type_str:
                            param = APIParameter(
                                name=str(row[0]),
                                type=type_str,
                                required="필수" in type_str,
                                description=str(row[2]) if row[2] else "",
                            )
                            if in_basic_section:
                                basic_params.append(param)
                            else:
                                request_params.append(param)

                return APISpec(
                    service_id=service_id,
                    endpoint=endpoint,
                    endpoint_url=endpoint_url,
                    basic_params=basic_params,
                    request_params=request_params,
                )

            except (openpyxl.utils.exceptions.InvalidFileException, KeyError, IndexError) as e:
                raise SpecParseError(f"Failed to parse spec for {service_id}: {e}") from e

        return await asyncio.to_thread(_parse_sync)

    def _extract_endpoint_url(self, worksheet) -> str | None:
        """
        Extract endpoint URL from worksheet.

        Args:
            worksheet: openpyxl worksheet object

        Returns:
            Endpoint URL or None if not found
        """
        for row in worksheet.iter_rows(min_row=1, max_row=50, max_col=1):
            cell = row[0]
            if cell.value and "요청주소" in str(cell.value):
                # Next row should contain the URL
                next_row_value = worksheet.cell(cell.row + 1, 1).value
                if next_row_value and "https://" in str(next_row_value):
                    url = str(next_row_value).strip().replace("- ", "")
                    return url
        return None

    def clear_cache(self, service_id: str | None = None):
        """
        Clear cached spec files.

        Args:
            service_id: If provided, only clear cache for this service.
                       If None, clear all cached specs.
        """
        if service_id:
            cache_file = self.cache_dir / f"{service_id}.xlsx"
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache for {service_id}")
        else:
            for file in self.cache_dir.glob("*.xlsx"):
                file.unlink()
            logger.info("Cleared all spec cache")
