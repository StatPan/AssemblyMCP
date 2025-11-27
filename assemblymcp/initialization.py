import json
import logging

from assembly_client.api import AssemblyAPIClient

logger = logging.getLogger(__name__)

# Service ID for the "Service List" (OPENSRVAPI)
# This API returns the list of all available APIs.
SERVICE_LIST_API_ID = "OPENSRVAPI"


async def ensure_master_list(client: AssemblyAPIClient) -> None:
    """
    Ensure the master list of APIs (all_apis.json) exists in the cache.
    If not, download it from the OPENSRVAPI service.

    Raises:
        RuntimeError: If the master list cannot be downloaded or is invalid.
    """
    cache_dir = client.spec_parser.cache_dir
    master_file = cache_dir / "all_apis.json"

    if master_file.exists():
        logger.info(f"Master list found at {master_file}")
        return

    logger.info(f"Master list not found at {master_file}. Downloading...")

    try:
        # Directly construct URL since we can't use client.get_data
        # (it depends on the master list for ID resolution)
        url = f"{client.BASE_URL}/{SERVICE_LIST_API_ID}"
        params = {
            "KEY": client.api_key,
            "Type": "json",
            "pIndex": 1,
            "pSize": 1000,  # Fetch all (there are ~270, so 1000 is safe)
        }

        logger.info(f"Fetching service list from {url}")
        response = await client.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Validate response
        if SERVICE_LIST_API_ID not in data:
            if "RESULT" in data:
                code = data["RESULT"].get("CODE")
                msg = data["RESULT"].get("MESSAGE")
                raise RuntimeError(f"Failed to fetch master list: {code} - {msg}")
            raise RuntimeError(f"Invalid response format for master list: {data.keys()}")

        # Save to file
        with open(master_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Successfully saved master list to {master_file}")

        # Reload the client's service maps
        # NOTE: This is a workaround as the assembly_client library doesn't provide
        # a public API to reload specs. If the library is updated, consider using
        # a public method instead of directly modifying internal attributes.
        from assembly_client.parser import load_service_map, load_service_metadata

        client.service_map = load_service_map(cache_dir)
        client.name_to_id = {name: sid for sid, name in client.service_map.items()}
        client.service_metadata = load_service_metadata(cache_dir)

        logger.info(f"Reloaded service map: {len(client.service_map)} services found.")

    except Exception as e:
        logger.error(f"Failed to initialize master list: {e}")
        # Re-raise the exception to prevent the server from starting in a broken state.
        raise
