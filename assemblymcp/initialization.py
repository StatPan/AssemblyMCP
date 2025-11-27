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
    """
    cache_dir = client.spec_parser.cache_dir
    master_file = cache_dir / "all_apis.json"

    if master_file.exists():
        # Optional: Check if it's empty or too old?
        # For now, just assume if it exists, it's good.
        logger.info(f"Master list found at {master_file}")
        return

    logger.info(f"Master list not found at {master_file}. Downloading...")

    try:
        # The OPENSRVAPI returns a list of all services.
        # We need to call it directly.
        # Note: We can't use client.get_data with ID resolution because
        # ID resolution depends on this file!
        # But client.get_data handles "Service ID" if we pass it directly?
        # Wait, client.get_data calls _resolve_service_id which checks service_map.
        # service_map is empty because file is missing.
        # So we must bypass _resolve_service_id or ensure it handles raw IDs.

        # Looking at api.py:
        # _resolve_service_id checks service_map, then name_to_id.
        # Then: "if len(service_id_or_name) > 10 and service_id_or_name.isalnum():
        # return service_id_or_name"
        # "OPENSRVAPI" is 10 chars. isalnum() is True.
        # Wait, > 10. "OPENSRVAPI" is exactly 10.
        # So _resolve_service_id might fail for "OPENSRVAPI" if strictly > 10.

        # Let's check the length of "OPENSRVAPI". It is 10.
        # If the check is `> 10`, it will fail.
        # We might need to manually construct the URL or patch the client behavior?
        # Or maybe "OPENSRVAPI" is a special case?

        # Let's try to fetch it manually using the client's http client if possible,
        # or just try get_data and see if it works (maybe it's in the hardcoded map?).
        # The client doesn't seem to have a hardcoded map.

        # Workaround: The endpoint for OPENSRVAPI is likely standard.
        # URL: https://open.assembly.go.kr/portal/openapi/OPENSRVAPI

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
            # Check for error
            if "RESULT" in data:
                code = data["RESULT"].get("CODE")
                msg = data["RESULT"].get("MESSAGE")
                raise RuntimeError(f"Failed to fetch master list: {code} - {msg}")
            raise RuntimeError(f"Invalid response format for master list: {data.keys()}")

        # Save to file
        # The client expects the raw JSON structure in all_apis.json
        with open(master_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Successfully saved master list to {master_file}")

        # Reload the client's maps
        # We need to access the private methods or just re-initialize?
        # Re-initializing the maps is safer.
        from assembly_client.parser import load_service_map, load_service_metadata

        client.service_map = load_service_map(cache_dir)
        client.name_to_id = {name: sid for sid, name in client.service_map.items()}
        client.service_metadata = load_service_metadata(cache_dir)

        logger.info(f"Reloaded service map: {len(client.service_map)} services found.")

    except Exception as e:
        logger.error(f"Failed to initialize master list: {e}")
        # We don't raise here to allow the server to start,
        # but list_api_services will fail.
        # Actually, we should probably log a loud warning.
