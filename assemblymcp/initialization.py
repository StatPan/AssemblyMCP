import json
import logging
import shutil
from pathlib import Path

from assembly_client.api import AssemblyAPIClient

logger = logging.getLogger(__name__)

# Service ID for the "Service List" (OPENSRVAPI)
# This API returns the list of all available APIs.
SERVICE_LIST_API_ID = "OPENSRVAPI"


async def ensure_master_list(client: AssemblyAPIClient) -> None:
    """
    Ensure the master list of APIs (all_apis.json) exists in the cache.
    1. Try to copy from the bundled specs in the package.
    2. If not found, try to download from the OPENSRVAPI service.

    Raises:
        RuntimeError: If the master list cannot be obtained.
    """
    cache_dir = client.spec_parser.cache_dir
    master_file = cache_dir / "all_apis.json"

    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 1. Check if master file already exists in cache
    if master_file.exists() and master_file.stat().st_size > 1000:
        logger.info(f"Master list found at {master_file}")
        return

    # 2. Try to copy from bundled specs (AssemblyMCP/assemblymcp/specs/all_apis.json)
    bundled_file = Path(__file__).parent / "specs" / "all_apis.json"
    if bundled_file.exists():
        logger.info(f"Copying bundled master list from {bundled_file} to {master_file}")
        shutil.copy(bundled_file, master_file)
        
        # Reload maps after copy
        _reload_client_maps(client, cache_dir)
        return

    # 3. Fallback: Download from API (Requires ASSEMBLY_API_KEY)
    logger.info(f"Master list not found. Attempting to download...")
    if not client.api_key:
        logger.warning("ASSEMBLY_API_KEY is missing. Only limited tools will be available.")
        return

    try:
        url = f"{client.BASE_URL}/{SERVICE_LIST_API_ID}"
        params = {
            "KEY": client.api_key,
            "Type": "json",
            "pIndex": 1,
            "pSize": 1000,
        }

        logger.info(f"Fetching service list from {url}")
        response = await client.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if SERVICE_LIST_API_ID not in data:
            raise RuntimeError(f"Invalid response format for master list")

        with open(master_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        _reload_client_maps(client, cache_dir)
        logger.info(f"Successfully downloaded and reloaded master list.")

    except Exception as e:
        logger.error(f"Failed to initialize master list: {e}")
        raise


def _reload_client_maps(client: AssemblyAPIClient, cache_dir: Path) -> None:
    """Helper to reload client service maps from cache directory."""
    from assembly_client.parser import load_service_map, load_service_metadata

    client.service_map = load_service_map(cache_dir)
    client.name_to_id = {name: sid for sid, name in client.service_map.items()}
    client.service_metadata = load_service_metadata(cache_dir)
    logger.info(f"Reloaded service map: {len(client.service_map)} services found.")