#!/usr/bin/env python3
"""
Script to synchronize API specifications.
Downloads and updates Excel spec files for all services.
"""

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

from assemblymcp.spec_parser import SpecParser

# Load environment variables
load_dotenv()

# Project root for spec file paths
project_root = Path(__file__).parent.parent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MASTER_LIST_SERVICE_ID = "OOBAOA001213RL17443"
BASE_URL = "https://open.assembly.go.kr/portal/openapi"


# Hardcoded endpoint for "OPEN API 전체 현황" (OOBAOA001213RL17443)
# This is needed to bootstrap the discovery process.
# In a real scenario, we might want to parse this from a spec, but we need the spec first.
# This endpoint is relatively stable.
async def fetch_master_list(api_key: str, parser: SpecParser) -> list[dict]:
    """Fetch the complete list of APIs from the master service."""

    # 1. Bootstrap: Get the endpoint for the Master List Service
    try:
        logger.info(
            f"Bootstrapping: Downloading spec for Master List Service ({MASTER_LIST_SERVICE_ID})..."
        )
        # Force download to ensure we have the latest spec for the master list itself
        # Use infSeq=1 for this specific service as per previous observation
        await parser.download_if_changed(MASTER_LIST_SERVICE_ID, inf_seq=1)
        spec = await parser.parse_spec(MASTER_LIST_SERVICE_ID)
        master_endpoint = spec.endpoint
        logger.info(f"Resolved Master List Endpoint: {master_endpoint}")
    except Exception as e:
        logger.error(f"Failed to resolve master list endpoint: {e}", exc_info=True)
        raise

    all_rows = []
    p_index = 1
    p_size = 100

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            url = f"{BASE_URL}/{master_endpoint}"
            params = {
                "KEY": api_key,
                "Type": "json",
                "pIndex": p_index,
                "pSize": p_size,
            }

            try:
                logger.info(f"Fetching master list page {p_index}...")
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # Check for error/info codes
                # The response key matches the service ID (e.g., OOBAOA001213RL17443)
                if MASTER_LIST_SERVICE_ID in data:
                    # Extract rows
                    # Structure: { service_id: [ {head}, {row: []} ] }
                    service_data = data[MASTER_LIST_SERVICE_ID]
                    if len(service_data) > 1 and "row" in service_data[1]:
                        rows = service_data[1]["row"]
                        all_rows.extend(rows)

                        if len(rows) < p_size:
                            break  # Last page
                        p_index += 1
                    else:
                        break  # No more data
                else:
                    # Check for error in response
                    if "RESULT" in data:
                        logger.error(f"API Error: {data['RESULT']}")
                    else:
                        logger.error(f"Unexpected response format: {data.keys()}")
                    break

            except Exception as e:
                logger.error(f"Failed to fetch master list page {p_index}: {e}")
                break

    return all_rows


def save_master_list(rows: list[dict], specs_dir: Path):
    """Save master list to a single JSON file."""
    output_file = specs_dir / "all_apis.json"

    wrapper = {
        "OPENSRVAPI": [
            {
                "head": [
                    {"list_total_count": len(rows)},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}},
                ]
            },
            {"row": rows},
        ]
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(wrapper, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(rows)} APIs to {output_file}")


def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe for filenames."""
    # Remove invalid characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    return name


def load_service_map(specs_dir: Path) -> dict[str, str]:
    """Load service ID to Name mapping from master list."""
    service_map = {}

    # Load from all_apis.json (new) or all_apis_p*.json (old)
    spec_files = list(specs_dir.glob("all_apis.json")) + list(specs_dir.glob("all_apis_p*.json"))

    for spec_file in spec_files:
        try:
            with open(spec_file, encoding="utf-8") as f:
                data = json.load(f)
                if "OPENSRVAPI" in data:
                    for item in data["OPENSRVAPI"]:
                        if "row" in item:
                            for row in item["row"]:
                                inf_id = row.get("INF_ID")
                                inf_nm = row.get("INF_NM")
                                if inf_id and inf_nm:
                                    service_map[inf_id] = inf_nm
        except Exception as e:
            logger.error(f"Failed to load spec file {spec_file}: {e}")

    return service_map


async def sync_service(parser: SpecParser, service_id: str, service_name: str | None) -> str:
    """
    Sync a single service by parsing its spec (downloads if not cached).
    Returns status: 'updated', 'failed'
    """
    try:
        # parse_spec handles caching internally:
        # 1. Checks cache first
        # 2. Downloads to memory if not cached
        # 3. Saves to cache as JSON
        await parser.parse_spec(service_id)
        return "updated"

    except Exception as e:
        logger.error(f"Failed to sync {service_id}: {e}")
        return "failed"


async def main():
    parser = argparse.ArgumentParser(description="Sync API specifications")
    parser.add_argument("--service-id", help="Sync specific service ID only")
    parser.add_argument("--limit", type=int, help="Limit number of services to sync")
    parser.add_argument(
        "--sync-list",
        action="store_true",
        help="Fetch and update master API list first",
    )
    parser.add_argument("--api-key", help="API Key for fetching master list")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if master list is unchanged",
    )
    args = parser.parse_args()

    # Setup directories
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    specs_dir = project_root / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    # Initialize parser (uses user cache dir by default)
    spec_parser = SpecParser()
    logger.info(f"Using cache directory: {spec_parser.cache_dir}")

    # Load service IDs from master list
    service_map = {}
    if args.service_id:
        # If specific ID requested, try to find its name if possible, otherwise None
        full_map = load_service_map(specs_dir)
        service_map = {args.service_id: full_map.get(args.service_id)}
    else:
        logger.info("Loading service IDs from specs directory...")
        service_map = load_service_map(specs_dir)
        logger.info(f"Found {len(service_map)} services.")

    service_ids = sorted(service_map.keys())
    if args.limit:
        service_ids = service_ids[: args.limit]

    logger.info(f"Starting sync for {len(service_ids)} services to cache...")

    stats = {"updated": 0, "failed": 0}

    # Process in chunks
    chunk_size = 5
    for i in range(0, len(service_ids), chunk_size):
        chunk = service_ids[i : i + chunk_size]
        tasks = [sync_service(spec_parser, sid, service_map.get(sid)) for sid in chunk]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                stats["failed"] += 1
            elif result == "updated":
                stats["updated"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"Progress: {i + len(chunk)}/{len(service_ids)} "
            f"(Updated: {stats['updated']}, Failed: {stats['failed']})"
        )

    logger.info("\n=== Sync Complete ===")
    logger.info(f"Updated: {stats['updated']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"Cache directory: {spec_parser.cache_dir}")


if __name__ == "__main__":
    asyncio.run(main())
