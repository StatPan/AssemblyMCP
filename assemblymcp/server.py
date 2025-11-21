"""MCP Server for Korean National Assembly API"""

import json
import logging

from fastmcp import FastMCP

from assemblymcp.client import AssemblyAPIClient, AssemblyAPIError
from assemblymcp.models import Bill, BillDetail
from assemblymcp.services import BillService, DiscoveryService, MeetingService, MemberService
from assemblymcp.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("AssemblyMCP")

# Initialize API Client globally to load specs once
client = AssemblyAPIClient(api_key=settings.assembly_api_key)

# Initialize Services
discovery_service = DiscoveryService(client)
bill_service = BillService(client)
member_service = MemberService(client)
meeting_service = MeetingService(client)


@mcp.tool()
async def get_assembly_info() -> str:
    """
    Get basic information about the Korean National Assembly API.

    Returns:
        Information about available API endpoints and configuration status.
        Also provides a recommended workflow for using the tools.
    """
    api_key_status = "configured" if settings.assembly_api_key else "not configured"
    service_count = len(client.specs)
    return (
        f"Korean National Assembly Open API MCP Server\n"
        f"API Key: {api_key_status}\n"
        f"Available Services: {service_count}\n\n"
        f"Recommended Workflow:\n"
        f"1. Find bills: Use 'search_bills(keyword)' or 'get_recent_bills()'.\n"
        f"2. Get details: Use 'get_bill_details(bill_id)' with the ID from step 1 "
        f"to see the summary and proposal reason.\n"
        f"3. Check members: Use 'get_member_info(name)' to see who proposed it.\n"
        f"4. Check meetings: Use 'get_meeting_records(bill_id)' to see discussion history.\n"
        f"5. Advanced: Use 'get_bill_info' for specific filtering or 'list_api_services' "
        f"to explore other datasets."
    )


@mcp.tool()
async def list_api_services(keyword: str = "") -> list[dict[str, str]]:
    """
    Search for available API services by keyword.
    Use this ONLY if the high-level tools (search_bills, get_bill_details) don't meet your needs.

    Args:
        keyword: Keyword to search in service name or description.

    Returns:
        List of services matching the keyword. Each item contains id, name, and description.
    """
    return await discovery_service.list_services(keyword)


@mcp.tool()
async def call_api_raw(service_id: str, params: str = "{}") -> str:
    """
    Call a specific API service with raw parameters.
    Use this ONLY for advanced usage when you need data not covered by other tools.

    Args:
        service_id: The ID of the service to call (e.g., 'OO1X9P001017YF13038').
        params: JSON string of query parameters (e.g., '{"pSize": 5}').

    Returns:
        Raw JSON response as a string.
    """
    try:
        param_dict = json.loads(params)
    except json.JSONDecodeError:
        return "Error: params must be a valid JSON string."

    try:
        data = await discovery_service.call_raw(service_id=service_id, params=param_dict)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except AssemblyAPIError as e:
        logger.error(f"API error calling service '{service_id}': {e}")
        return f"API Error: {e}"
    except Exception:
        logger.exception(f"Unexpected error calling API service '{service_id}'")
        return "An unexpected error occurred."


@mcp.tool()
async def get_bill_info(
    age: str = "22",
    bill_id: str | None = None,
    bill_name: str | None = None,
    propose_dt: str | None = None,
    proc_status: str | None = None,
    limit: int = 10,
) -> list[Bill]:
    """
    Advanced search for legislative bills with specific filters.
    Use this when you need to filter by specific fields like ID, date, or status.
    For general keyword search, use 'search_bills' instead.

    Args:
        age: 대 (AGE). Defaults to "22" (current session).
        bill_id: 의안ID (BILL_ID/BILL_NO).
        bill_name: 의안명 (BILL_NAME).
        propose_dt: 제안일자 (PROPOSE_DT). YYYYMMDD format.
        proc_status: 처리상태 (PROC_STATUS).
        limit: Max results (default 10).

    Returns:
        List of Bill objects.
    """
    return await bill_service.get_bill_info(
        age=age,
        bill_id=bill_id,
        bill_name=bill_name,
        propose_dt=propose_dt,
        proc_status=proc_status,
        limit=limit,
    )


@mcp.tool()
async def search_bills(keyword: str) -> list[Bill]:
    """
    Search for bills by keyword.
    Automatically searches the current legislative session (22nd),
    and falls back to the previous session (21st) if no results are found.

    IMPORTANT: This tool returns a list of bills with basic info (ID, title, proposer).
    To get the full text, summary, or proposal reason, you MUST take the 'bill_id'
    from the result and call 'get_bill_details(bill_id)'.

    Args:
        keyword: Search term (e.g., "artificial intelligence", "budget").

    Returns:
        List of matching bills.
    """
    return await bill_service.search_bills(keyword)


@mcp.tool()
async def get_recent_bills(limit: int = 10) -> list[Bill]:
    """
    Get the most recently proposed bills.
    Useful for answering "what's new" or "latest bills".

    IMPORTANT: This tool returns a list of bills with basic info.
    To get the full text, summary, or proposal reason, you MUST take the 'bill_id'
    from the result and call 'get_bill_details(bill_id)'.

    Args:
        limit: Number of bills to return (default 10).

    Returns:
        List of bills sorted by proposal date (newest first).
    """
    return await bill_service.get_recent_bills(limit)


@mcp.tool()
async def get_bill_details(bill_id: str) -> BillDetail | None:
    """
    Get detailed information about a specific bill.
    Includes the bill's summary (main content) and reason for proposal.

    Usage:
    1. Search for bills using 'search_bills' or 'get_recent_bills'.
    2. Copy the 'bill_id' from the result.
    3. Call this tool with that 'bill_id'.

    Args:
        bill_id: The ID of the bill (e.g., '2100001').

    Returns:
        BillDetail object containing summary and reason, or None if not found.
    """
    return await bill_service.get_bill_details(bill_id)


@mcp.tool()
async def get_member_info(name: str) -> list[dict]:
    """
    Search for detailed information about a National Assembly member.
    Useful for finding out who a proposer is, their party, and their constituency.

    Args:
        name: Name of the member (e.g., "홍길동").

    Returns:
        List of member information dictionaries.
    """
    return await member_service.get_member_info(name)


@mcp.tool()
async def get_meeting_records(bill_id: str) -> list[dict]:
    """
    Get committee meeting records related to a specific bill.
    Useful for understanding the discussion and legislative history of a bill.

    Args:
        bill_id: The ID of the bill (e.g., '2100001').

    Returns:
        List of meeting records.
    """
    return await meeting_service.get_meeting_records(bill_id)


def main():
    """Run the MCP server"""
    # Validate settings on startup (but don't fail if API key is missing yet)
    if settings.assembly_api_key:
        print(f"[OK] API key configured: {settings.assembly_api_key[:8]}...")
    else:
        print("[WARNING] API key not configured. Set ASSEMBLY_API_KEY environment variable.")

    mcp.run()


if __name__ == "__main__":
    main()
