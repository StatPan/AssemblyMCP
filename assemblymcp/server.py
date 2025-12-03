"""MCP Server for Korean National Assembly API"""

from __future__ import annotations

import asyncio
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

from assemblymcp.initialization import ensure_master_list
from assemblymcp.schemas import bill_detail_output_schema, bill_list_output_schema
from assemblymcp.services import (
    BillService,
    CommitteeService,
    DiscoveryService,
    MeetingService,
    MemberService,
)
from assemblymcp.config import settings
from assemblymcp.middleware import CachingMiddleware, LoggingMiddleware, configure_logging

# Configure logging based on settings
configure_logging()
logger = logging.getLogger(__name__)

# Initialize FastMCP server
# CORS is automatically handled by FastMCP for Streamable HTTP
mcp = FastMCP("AssemblyMCP")

# Add Middleware (Order matters: Outer -> Inner)
# We want Caching to be checked first (Outer), then Logging (Inner) wraps the execution
mcp.add_middleware(CachingMiddleware())
mcp.add_middleware(LoggingMiddleware())

# Initialize API Client globally to load specs once
try:
    client = AssemblyAPIClient(api_key=settings.assembly_api_key)
except Exception as e:
    logger.error(f"Failed to initialize client: {e}")
    client = None


# Initialize Services
if client:
    try:
        asyncio.run(ensure_master_list(client))
    except Exception as e:
        logger.critical(f"Failed to initialize master list: {e}")
        raise RuntimeError("Could not initialize master API list. Server cannot start.") from e

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
    전체 요약 + 필수 사용 가이드.

    - 총 270여 개의 국회 OpenAPI를 모두 사용할 수 있습니다. 고수준 툴은 일부만 래핑하지만,
      list_api_services → get_api_spec → call_api_raw 조합으로 어떤 정보든 조회 가능합니다.
    - "이 기능은 없다"라고 답하지 마세요. 고수준 툴에 없으면 서비스를 검색해 직접 호출하거나
      연쇄 호출로 답을 구성하세요.
    - 예시: "위원회 구성원" → list_api_services("위원 명단")으로 서비스 찾기
      → get_api_spec(...)로 파라미터 확인 → call_api_raw(...) 호출
      → 필요하면 get_member_info로 의원 상세/연락처 보강.

    Returns basic server status plus 이 조합 워크플로우를 안내합니다.
    """
    if not client:
        return "Error: API Client not initialized. Please check API key configuration."

    try:
        api_key_status = "configured" if settings.assembly_api_key else "not configured"
        service_count = len(client.service_map)
        return (
            "AssemblyMCP – Korean National Assembly Open API\n"
            f"API Key: {api_key_status}\n"
            f"Available Services (raw): {service_count} (≈270 OpenAPI endpoints)\n\n"
            "핵심 원칙: 고수준 툴에 없다고 끝내지 말 것. 항상 list_api_services → "
            "get_api_spec → call_api_raw 조합으로 우회 가능합니다.\n\n"
            "빠른 워크플로우 예시:\n"
            "1) 의안: search_bills/get_recent_bills → get_bill_details → "
            "get_meeting_records(토론) → get_member_info(발의자 상세)\n"
            "2) 위원회 구성원: list_api_services('위원 명단') → get_api_spec → "
            "call_api_raw → 필요 시 get_member_info로 개인 정보 보강\n"
            "3) 기타 데이터: list_api_services(keyword)로 서비스 ID 확보 후 "
            "get_api_spec에서 필수 파라미터 확인 → call_api_raw로 직접 호출\n\n"
            "항상: 특정 주제에 맞는 서비스가 안 보이면 키워드를 바꿔 여러 번 검색하고, "
            "도구가 없다거나 불가능하다고 답하지 마세요."
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
    모든 OpenAPI(총 270여 개) 메타데이터를 검색합니다.

    - 고수준 툴에 없다고 끝내지 말고, 여기서 서비스 ID를 찾은 뒤
      get_api_spec → call_api_raw 로 직접 호출하세요.
    - 키워드는 넓게 잡으세요. 국문/영문, 띄어쓰기/부분 문자열 모두 시도해볼 것.

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
    모든 국회 OpenAPI를 직접 호출하는 만능 백도어입니다.

    - "해당 기능이 없다"는 답을 피하기 위해 항상 이 경로를 고려하세요.
    - 절차: list_api_services로 ID 찾기 → get_api_spec로 파라미터 확인 → 여기서 호출.
    - 응답을 받은 뒤, 필요한 경우 다른 고수준 툴(예: get_member_info, get_meeting_records)로
      후속 검색을 연쇄 호출해 답을 완성하세요.

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
    위원회 목록과 기본 정보.

    - 위원 명단(구성원)까지 필요하면 고수준 툴에 없더라도 포기하지 마세요.
      예: list_api_services("위원 명단") → get_api_spec(...) → call_api_raw(...)로 명단 조회,
      이후 get_member_info로 개인 상세 보강.
    - 이 함수는 정확한 위원회명/코드를 찾을 때 사용하고, 명단/일정 등은 raw 호출로 이어가세요.

    Args:
        committee_name: Optional name to filter by (e.g., "법제사법위원회").

    Returns:
        List of committee information objects.
    """
    service = _require_service(committee_service)
    committees = await service.get_committee_list(committee_name)
    return [c.model_dump() for c in committees]


@mcp.tool()
async def get_committee_members(
    committee_code: str | None = None,
    committee_name: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    위원회 구성원(위원 명단)을 조회합니다.

    - committee_code(HR_DEPT_CD)나 committee_name으로 조회 가능합니다.
    - 위원회명이 불명확하면 먼저 get_committee_list로 정확한 이름/코드를 찾으세요.
    - 결과의 개별 의원 상세 정보가 필요하면 get_member_info를 조합하세요.
    - 다른 위원회 관련 데이터(일정, 회의록 등)는 list_api_services → get_api_spec → call_api_raw
      흐름으로 추가 조회할 수 있습니다.
    """
    service = _require_service(committee_service)
    return await service.get_committee_members(
        committee_code=committee_code,
        committee_name=committee_name,
        page=page,
        limit=limit,
    )


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
