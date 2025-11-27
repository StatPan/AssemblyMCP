"""MCP Server for Korean National Assembly API"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Any, TypeVar

os.environ.setdefault("FASTMCP_LOG_ENABLED", "false")

# Configure logging to file to avoid polluting stdout/stderr (breaks MCP protocol)
import tempfile
from pathlib import Path

from assembly_client.api import AssemblyAPIClient
from assembly_client.errors import AssemblyAPIError, SpecParseError
from fastmcp import FastMCP

from assemblymcp.schemas import bill_detail_output_schema, bill_list_output_schema
from assemblymcp.services import (
    BillService,
    CommitteeService,
    DiscoveryService,
    MeetingService,
    MemberService,
)
from assemblymcp.settings import settings

log_dir = Path(tempfile.gettempdir()) / "assemblymcp"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "server.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=str(log_file),
    filemode="a",
)

logger = logging.getLogger(__name__)

# Initialize FastMCP server
# CORS is automatically handled by FastMCP for Streamable HTTP
mcp = FastMCP("AssemblyMCP")

# Initialize API Client globally to load specs once
try:
    client = AssemblyAPIClient(api_key=settings.assembly_api_key)
except Exception as e:
    logger.error(f"Failed to initialize client: {e}")
    client = None

# Initialize Services
if client:
    discovery_service = DiscoveryService(client)
    bill_service = BillService(client)
    member_service = MemberService(client)
    meeting_service = MeetingService(client)
    committee_service = CommitteeService(client)
else:
    discovery_service = None
    bill_service = None
    member_service = None
    meeting_service = None
    committee_service = None

ServiceT = TypeVar("ServiceT")


def _require_service[ServiceT](service: ServiceT | None) -> ServiceT:
    """Ensure the API client and requested service are available."""
    if service is None:
        raise RuntimeError(
            "Assembly API client is not ready. "
            "Set the ASSEMBLY_API_KEY environment variable and restart the server."
        )
    return service


@mcp.tool()
async def ping() -> str:
    """Check if server is alive."""
    return "pong"


@mcp.tool()
async def get_assembly_info() -> str:
    """
    Get basic information about the Korean National Assembly API.

    Returns:
        Information about available API endpoints and configuration status.
        Also provides a recommended workflow for using the tools.
    """
    if not client:
        return "Error: API Client not initialized. Please check API key configuration."

    try:
        api_key_status = "configured" if settings.assembly_api_key else "not configured"
        service_count = len(client.service_map)
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
    except Exception as e:
        traceback.print_exc()
        return f"Error getting assembly info: {e}"


@mcp.tool()
async def get_api_spec(service_id: str) -> dict[str, Any]:
    """
    Get detailed specification for a specific API service.

    This returns the complete API specification including endpoint URL,
    request parameters with types/constraints, and response structure.
    Useful for dynamic API exploration when high-level tools don't meet your needs.

    Workflow:
    1. Use 'list_api_services(keyword)' to find service IDs
    2. Call this tool with the service_id to see parameter details
    3. Use 'call_api_raw(service_id, params)' to make custom API calls

    Args:
        service_id: The service ID (e.g., 'O4K6HM0012064I15889')

    Returns:
        Complete API specification including parameters and endpoint
    """
    if not client:
        raise RuntimeError("API client not initialized")

    try:
        spec = await client.spec_parser.parse_spec(service_id)
        return spec.to_dict()
    except SpecParseError as e:
        logger.error(f"Failed to parse spec for {service_id}: {e}")
        return {
            "error": str(e),
            "error_type": "SpecParseError",
            "service_id": service_id,
            "help": (
                "스펙 파일 다운로드 또는 파싱에 실패했습니다.\n"
                "공공데이터 포털의 일시적 오류이거나 스펙 파일 형식이 변경되었을 수 있습니다."
            ),
            "suggested_action": "Try again later or check data.go.kr",
        }
    except Exception as e:
        logger.error(f"Unexpected error getting spec for {service_id}: {e}", exc_info=True)

        # Provide detailed troubleshooting information
        cache_dir = "unknown"
        if hasattr(client.spec_parser, "cache_dir"):
            cache_dir = str(client.spec_parser.cache_dir)

        error_response = {
            "error": str(e),
            "error_type": type(e).__name__,
            "service_id": service_id,
            "help": (
                "예상치 못한 오류가 발생했습니다. 로그를 확인해주세요.\n\n"
                "가능한 원인:\n"
                "1. 네트워크 문제\n"
                "2. 서비스 ID가 유효하지 않음\n"
                "3. 파일 시스템 권한 문제"
            ),
            "spec_cache_location": cache_dir,
            "suggested_action": "Try: list_api_services(keyword='') to see all available services",
        }

        return error_response


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
    service = _require_service(discovery_service)
    return await service.list_services(keyword)


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
        service = _require_service(discovery_service)
        data = await service.call_raw(service_id_or_name=service_id, params=param_dict)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except AssemblyAPIError as e:
        logger.error(f"API error calling service '{service_id}': {e}")
        return f"API Error: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error calling API service '{service_id}'")
        error_type = type(e).__name__
        error_msg = str(e)
        return f"Error ({error_type}): {error_msg}"


@mcp.tool(output_schema=bill_list_output_schema())
async def get_bill_info(
    age: str = "22",
    bill_id: str | None = None,
    bill_name: str | None = None,
    propose_dt: str | None = None,
    proc_status: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]]:
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
        page: Page number (default 1).
        limit: Max results (default 10).

    Returns:
        List of Bill objects.
    """
    service = _require_service(bill_service)
    bills = await service.get_bill_info(
        age=age,
        bill_id=bill_id,
        bill_name=bill_name,
        propose_dt=propose_dt,
        proc_status=proc_status,
        page=page,
        limit=limit,
    )
    return [bill.model_dump() for bill in bills]


@mcp.tool(output_schema=bill_list_output_schema())
async def search_bills(keyword: str, page: int = 1, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search for bills by keyword.
    Automatically searches the current legislative session (22nd),
    and falls back to the previous session (21st) if no results are found.

    IMPORTANT: This tool returns a list of bills with basic info (ID, title, proposer).
    To get the full text, summary, or proposal reason, you MUST take the 'bill_id'
    from the result and call 'get_bill_details(bill_id)'.

    Args:
        keyword: Search term (e.g., "artificial intelligence", "budget").
        page: Page number (default 1).
        limit: Max results (default 10).

    Returns:
        List of matching bills.
    """
    service = _require_service(bill_service)
    bills = await service.search_bills(keyword, page=page, limit=limit)
    return [bill.model_dump() for bill in bills]


@mcp.tool(output_schema=bill_list_output_schema())
async def get_recent_bills(page: int = 1, limit: int = 10) -> list[dict[str, Any]]:
    """
    Get the most recently proposed bills.
    Useful for answering "what's new" or "latest bills".

    IMPORTANT: This tool returns a list of bills with basic info.
    To get the full text, summary, or proposal reason, you MUST take the 'bill_id'
    from the result and call 'get_bill_details(bill_id)'.

    Args:
        page: Page number (default 1).
        limit: Number of bills to return (default 10).

    Returns:
        List of bills sorted by proposal date (newest first).
    """
    service = _require_service(bill_service)
    bills = await service.get_recent_bills(page=page, limit=limit)
    return [bill.model_dump() for bill in bills]


@mcp.tool(output_schema=bill_detail_output_schema())
async def get_bill_details(bill_id: str, age: str | None = None) -> dict[str, Any] | None:
    """
    Get detailed information about a specific bill.
    Includes the bill's summary (main content) and reason for proposal.

    Usage:
    1. Search for bills using 'search_bills' or 'get_recent_bills'.
    2. Copy the 'bill_id' from the result.
    3. Call this tool with that 'bill_id'.

    Args:
        bill_id: The ID of the bill (e.g., '2100001').
        age: Optional legislative session age (e.g., "22"). If provided, skips probing.

    Returns:
        BillDetail object containing summary and reason, or None if not found.
    """
    service = _require_service(bill_service)
    details = await service.get_bill_details(bill_id, age=age)
    return details.model_dump() if details else None


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
    service = _require_service(member_service)
    return await service.get_member_info(name)


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
    service = _require_service(meeting_service)
    return await service.get_meeting_records(bill_id)


@mcp.tool()
async def search_meetings(
    committee_name: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search for committee meetings.

    Note: This API often returns empty results due to strict filtering or limited data availability.
    For better results:
    - Use recent dates (within last 6 months)
    - Try without date filters first to see available data
    - Use get_committee_list() to get exact committee names
    - Be aware that meeting data may not be immediately available after meetings

    Args:
        committee_name: Name of the committee (e.g., "법제사법위원회").
        date_start: Start date (YYYY-MM-DD).
        date_end: End date (YYYY-MM-DD).
        page: Page number (default 1).
        limit: Max results (default 10).

    Returns:
        List of meeting records.
    """
    service = _require_service(meeting_service)
    return await service.search_meetings(
        committee_name=committee_name,
        date_start=date_start,
        date_end=date_end,
        page=page,
        limit=limit,
    )


@mcp.tool()
async def get_committee_list(committee_name: str | None = None) -> list[dict[str, Any]]:
    """
    Get a list of committees.
    Useful for finding the correct committee name or code for filtering.

    Args:
        committee_name: Optional name to filter by (e.g., "법제사법위원회").

    Returns:
        List of committee information objects.
    """
    service = _require_service(committee_service)
    committees = await service.get_committee_list(committee_name)
    return [c.model_dump() for c in committees]


def main():
    """Run the MCP server"""
    sys.stdout.reconfigure(line_buffering=True)
    # Validate settings on startup (but don't fail if API key is missing yet)
    if not settings.assembly_api_key:
        logger.warning(
            "ASSEMBLY_API_KEY is not configured. The server will run but tools will fail."
        )

    # Check for transport configuration
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    # Normalize transport names
    if transport in ("http", "streamable-http", "sse"):
        # Use Streamable HTTP (the new standard, replacing SSE)
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8000"))
        path = os.getenv("MCP_PATH", "/mcp")

        logger.info(f"Starting AssemblyMCP with Streamable HTTP on {host}:{port}{path}")
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        # Default to stdio for local/desktop usage
        logger.info("Starting AssemblyMCP in stdio mode")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
