#!/usr/bin/env python3
"""
Script to synchronize API specifications.
Downloads and updates Excel spec files for all services.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from assemblymcp.spec_parser import SpecParser  # noqa: E402

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
        logger.error(f"Failed to resolve master list endpoint: {e}")
        return []

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


def load_service_ids(specs_dir: Path) -> list[str]:
    """Load all service IDs from specs directory."""
    service_ids = set()

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
                                if inf_id:
                                    service_ids.add(inf_id)
        except Exception as e:
            logger.error(f"Failed to load spec file {spec_file}: {e}")

    return sorted(service_ids)


async def sync_service(parser: SpecParser, service_id: str, json_dir: Path) -> str:
    """
    Sync a single service.
    Returns status: 'updated', 'unchanged', 'failed'
    """
    try:
        # Download Excel (updates cache if changed)
        updated = await parser.download_if_changed(service_id)

        # Check if JSON exists
        json_file = json_dir / f"{service_id}.json"

        # If Excel updated OR JSON missing, parse and save JSON
        if updated or not json_file.exists():
            spec = await parser.parse_spec(service_id)
            parser.save_spec_json(spec, json_dir)
            return "updated"

        return "unchanged"
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

    specs_dir = project_root / "specs"

    # Use specs/excel for cache (gitignored ideally)
    excel_cache_dir = specs_dir / "excel"
    excel_cache_dir.mkdir(exist_ok=True)

    # Use specs/json for persistent repo storage
    json_dir = specs_dir / "json"
    json_dir.mkdir(exist_ok=True)

    spec_parser = SpecParser(cache_dir=excel_cache_dir)

    # 1. Master List Sync
    master_list_changed = False
    if args.sync_list:
        api_key = args.api_key or os.getenv("ASSEMBLY_API_KEY")
        if not api_key:
            logger.error("API Key required for sync-list. Set ASSEMBLY_API_KEY or pass --api-key")
            return

        logger.info("Fetching master API list...")

        # Load old IDs for diff
        old_ids = set(load_service_ids(specs_dir))

        rows = await fetch_master_list(api_key, spec_parser)
        if rows:
            save_master_list(rows, specs_dir)

            new_ids = {row["INF_ID"] for row in rows if "INF_ID" in row}

            # Diff
            added = new_ids - old_ids
            removed = old_ids - new_ids

            if added:
                logger.info(f"Found {len(added)} NEW APIs: {added}")
                master_list_changed = True
            if removed:
                logger.info(f"Found {len(removed)} DELETED APIs: {removed}")
                master_list_changed = True

            if not added and not removed:
                logger.info("No changes in API list.")
        else:
            logger.warning("No rows fetched from master list. Skipping update.")

    # 2. Load IDs (Reload to get new ones if we just synced)
    if args.service_id:
        service_ids = [args.service_id]
    else:
        # Optimization: If syncing list and it didn't change, and not forced, skip individual checks
        if args.sync_list and not master_list_changed and not args.force:
            logger.info(
                "Master list is unchanged. Skipping individual spec sync (use --force to override)."
            )
            return

        logger.info("Loading service IDs from specs directory...")
        service_ids = load_service_ids(specs_dir)
        logger.info(f"Found {len(service_ids)} services.")

    if args.limit:
        service_ids = service_ids[: args.limit]

    logger.info(f"Starting sync for {len(service_ids)} services...")

    stats = {"updated": 0, "unchanged": 0, "failed": 0}

    # Process in chunks
    chunk_size = 5
    for i in range(0, len(service_ids), chunk_size):
        chunk = service_ids[i : i + chunk_size]
        tasks = [sync_service(spec_parser, sid, json_dir) for sid in chunk]
        results = await asyncio.gather(*tasks)

        for res in results:
            stats[res] += 1

        await asyncio.sleep(0.5)

        if (i + chunk_size) % 20 == 0:
            logger.info(f"Progress: {i + chunk_size}/{len(service_ids)} - {stats}")

    logger.info("Sync completed!")
    logger.info(f"Final Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
