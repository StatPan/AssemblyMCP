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

from assembly_client.api import AssemblyAPIClient
from assembly_client.errors import AssemblyAPIError, SpecParseError
from fastmcp import FastMCP

from assemblymcp.config import settings
from assemblymcp.middleware import (
    CachingMiddleware,
    InitializationMiddleware,
    LoggingMiddleware,
    configure_logging,
)
from assemblymcp.schemas import bill_detail_output_schema, bill_list_output_schema
from assemblymcp.services import (
    BillService,
    CommitteeService,
    DiscoveryService,
    MeetingService,
    MemberService,
)

# Configure logging based on settings
configure_logging()
logger = logging.getLogger(__name__)

# Initialize API Client globally to load specs once
try:
    client = AssemblyAPIClient(api_key=settings.assembly_api_key)
except Exception as e:
    logger.error(f"Failed to initialize client: {e}")
    client = None

# Initialize FastMCP server
# CORS is automatically handled by FastMCP for Streamable HTTP
mcp = FastMCP("AssemblyMCP")

# Add Middleware (Order matters: last added is outermost)
# Logging (outer) wraps Init (middle) wraps Caching (inner)
mcp.add_middleware(CachingMiddleware())       # Was innermost
mcp.add_middleware(InitializationMiddleware(client))
mcp.add_middleware(LoggingMiddleware())


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
            "AssemblyMCP – 대한민국 국회 OpenAPI (Korean National Assembly Open API)\n"
            f"API 키 상태: {api_key_status}\n"
            f"사용 가능한 서비스(Raw): {service_count}개 (약 270개 엔드포인트)\n\n"
            "핵심 원칙: 고수준 툴에 기능이 없다고 검색을 중단하지 마세요.\n"
            "항상 다음 조합으로 해결 가능합니다.\n"
            "👉 list_api_services → get_api_spec → call_api_raw\n\n"
            "빠른 워크플로우 예시:\n"
            "1) 의안 검색: search_bills/get_recent_bills → get_bill_details → "
            "get_meeting_records(토론) → get_member_info(발의자 상세)\n"
            "2) 위원회 명단: list_api_services('위원 명단') → get_api_spec → "
            "call_api_raw → 필요 시 get_member_info로 인적사항 보강\n"
            "3) 기타 데이터: list_api_services(키워드)로 서비스 ID 확보 후 "
            "get_api_spec에서 필수 파라미터 확인 → call_api_raw로 직접 호출\n\n"
            "팁: 특정 주제에 맞는 서비스가 안 보이면 키워드를 바꿔 여러 번 검색하고, "
            "도구가 모자라거나 불가능하다고 섣불리 결론 내리지 마세요."
        )
    except Exception as e:
        traceback.print_exc()
        return f"Error getting assembly info: {e}"


@mcp.tool()
async def get_api_spec(service_id: str) -> dict[str, Any]:
    """
    특정 API 서비스의 상세 스펙을 조회합니다.

    이 툴은 엔드포인트 URL, 요청 파라미터(타입/제약조건), 응답 구조 등 전체 API 명세를 반환합니다.
    고수준 툴이 제공하지 않는 정보를 조회하기 위해 동적으로 API를 탐색할 때 유용합니다.

    기능:
    - 파라미터 제약조건 전체 반환.
    - **데이터 미리보기(Data Preview)**: 실제 데이터 1건을 조회하여 값의 형식을 보여줍니다.
    - **파라미터 힌트(Parameter Hints)**: 실제 데이터를 기반으로 유효한 입력값을 제안합니다
      (예: UNIT_CD="22대").

    워크플로우:
    1. 'list_api_services(keyword)'로 서비스 ID 검색
    2. 이 툴을 호출하여 파라미터 상세 확인
    3. 'call_api_raw(service_id, params)'로 맞춤형 API 호출

    Args:
        service_id: 서비스 ID (예: 'O4K6HM0012064I15889')

    Returns:
        파라미터와 엔드포인트를 포함한 전체 API 스펙
    """
    if not client:
        raise RuntimeError("API client not initialized")

    result = {}

    # 1. Parse Spec
    try:
        spec = await client.spec_parser.parse_spec(service_id)
        result = spec.to_dict()
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
        }
    except Exception as e:
        logger.error(f"Unexpected error getting spec for {service_id}: {e}", exc_info=True)

        cache_dir = "unknown"
        if hasattr(client.spec_parser, "cache_dir"):
            cache_dir = str(client.spec_parser.cache_dir)

        return {
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
            "suggested_action": "제안: list_api_services(keyword='')로 사용 가능한 서비스 확인",
        }

    # 2. Fetch Data Preview (Non-blocking)
    try:
        service = _require_service(discovery_service)
        sample = await service.get_preview_data(service_id)

        if sample:
            result["data_preview"] = {
                "description": "Actual data fetched from API (limit=1) for format reference.",
                "sample_row": sample,
            }

            # 3. Generate Parameter Hints
            # Cross-reference known request params with response keys
            hints = {}
            # Ensure 'request_parameter' exists and is a list
            req_params = result.get("request_parameter", [])
            if isinstance(req_params, list):
                for param in req_params:
                    # param is usually dict like {"name": "UNIT_CD", ...}
                    p_name = param.get("name")
                    if p_name and p_name in sample:
                        hints[p_name] = f"Example from data: '{sample[p_name]}'"

            if hints:
                result["parameter_hints"] = hints

    except Exception as e:
        # Don't fail the whole tool if preview fails
        logger.warning(f"Failed to add preview data for {service_id}: {e}")
        result["data_preview_error"] = str(e)

    return result


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
    다양한 필터를 사용하여 의안을 상세 검색합니다.
    ID, 날짜, 상태 등 특정 필드로 검색할 때 사용하세요.
    일반적인 키워드 검색은 'search_bills'를 사용하세요.

    Args:
        age: 대수 (예: "22"). 기본값은 "22" (현재 대수).
        bill_id: 의안ID (BILL_ID/BILL_NO).
        bill_name: 의안명 (BILL_NAME).
        propose_dt: 제안일자 (PROPOSE_DT). YYYYMMDD 형식.
        proc_status: 처리상태 (PROC_STATUS).
        page: 페이지 번호 (기본값 1).
        limit: 최대 결과 수 (기본값 10).

    Returns:
        의안 객체 목록.
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
    키워드로 의안을 검색합니다.
    자동으로 현재 대수(22대)를 검색하고, 결과가 없으면 이전 대수(21대)를 검색합니다.

    중요: 이 툴은 의안의 기본 정보(ID, 제목, 발의자)만 반환합니다.
    전문, 요약, 제안 이유 등 상세 내용은 'bill_id'를 사용하여 'get_bill_details(bill_id)'를
    호출해야 합니다.

    Args:
        keyword: 검색어 (예: "인공지능", "예산").
        page: 페이지 번호 (기본값 1).
        limit: 최대 결과 수 (기본값 10).

    Returns:
        검색된 의안 목록.
    """
    service = _require_service(bill_service)
    bills = await service.search_bills(keyword, page=page, limit=limit)
    return [bill.model_dump() for bill in bills]


@mcp.tool(output_schema=bill_list_output_schema())
async def get_recent_bills(page: int = 1, limit: int = 10) -> list[dict[str, Any]]:
    """
    최근 발의된 의안 목록을 조회합니다.
    '새로운 의안'이나 '최신 의안'을 파악할 때 유용합니다.

    중요: 이 툴은 의안의 기본 정보만 반환합니다.
    상세 내용은 'get_bill_details(bill_id)'를 사용하세요.

    Args:
        page: 페이지 번호 (기본값 1).
        limit: 반환할 의안 수 (기본값 10).

    Returns:
        발의일자 순으로 정렬된 의안 목록 (최신순).
    """
    service = _require_service(bill_service)
    bills = await service.get_recent_bills(page=page, limit=limit)
    return [bill.model_dump() for bill in bills]


@mcp.tool(output_schema=bill_detail_output_schema())
async def get_bill_details(bill_id: str, age: str | None = None) -> dict[str, Any] | None:
    """
    특정 의안의 상세 정보를 조회합니다.
    의안의 요약(주요 내용)과 제안 이유를 포함합니다.

    사용법:
    1. 'search_bills' 또는 'get_recent_bills'로 의안 검색
    2. 결과에서 'bill_id' 복사
    3. 이 툴에 'bill_id'를 전달하여 호출

    Args:
        bill_id: 의안 ID (예: '2100001').
        age: 선택적 대수 (예: "22"). 제공 시 탐색 과정을 건너뜁니다.

    Returns:
        요약과 제안 이유가 포함된 BillDetail 객체, 또는 없으면 None.
    """
    service = _require_service(bill_service)
    details = await service.get_bill_details(bill_id, age=age)
    return details.model_dump() if details else None


@mcp.tool()
async def get_member_info(name: str) -> list[dict]:
    """
    국회의원 상세 정보를 검색합니다.
    발의자가 누구인지, 소속 정당, 지역구 등을 파악할 때 유용합니다.

    Args:
        name: 의원명 (예: "홍길동").

    Returns:
        국회의원 정보 목록.
    """
    service = _require_service(member_service)
    return await service.get_member_info(name)


@mcp.tool()
async def get_meeting_records(bill_id: str) -> list[dict]:
    """
    특정 의안과 관련된 위원회 회의록을 조회합니다.
    의안에 대한 논의 내용과 입법 연혁을 파악할 때 유용합니다.

    Args:
        bill_id: 의안 ID (예: '2100001').

    Returns:
        회의록 목록.
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
    위원회 회의를 검색합니다.

    참고: 엄격한 필터링이나 데이터 부족으로 인해 빈 결과가 자주 나올 수 있습니다.
    더 나은 결과를 위해:
    - 최근 날짜 사용 (지난 6개월 이내)
    - 날짜 필터 없이 조회하여 가용 데이터 확인
    - get_committee_list()로 정확한 위원회 명칭 확인
    - 회의 직후에는 데이터가 바로 제공되지 않을 수 있음을 인지

    Args:
        committee_name: 위원회명 (예: "법제사법위원회").
        date_start: 시작일 (YYYY-MM-DD).
        date_end: 종료일 (YYYY-MM-DD).
        page: 페이지 번호 (기본값 1).
        limit: 최대 결과 수 (기본값 10).

    Returns:
        회의록 목록.
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
async def get_plenary_schedule(
    unit_cd: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    본회의 일정을 조회합니다. (Service ID: ORDPSW001070QH19059)

    - unit_cd(대수) 파라미터가 중요합니다. (예: "22")
    - 데이터가 없는 경우도 많으니 빈 결과가 나오면 대수를 변경하거나 생략해보세요.

    Args:
        unit_cd: 대수 (예: "22"). 생략 시 전체 조회될 수 있음.
        page: Page number (default 1).
        limit: Max results (default 10).
    """
    service = _require_service(meeting_service)
    return await service.get_plenary_schedule(unit_cd=unit_cd, page=page, limit=limit)


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

    사용 팁:
    1. 먼저 'committee_name'만 사용하여 위원 명단을 조회해 볼 수 있습니다.
    2. 만약 결과가 없거나 에러가 발생하면, 이는 정확한 매칭이 아니거나 해당 위원회의 데이터가
       존재하지 않을 수 있음을 의미합니다.
    3. 이 경우 'get_committee_list' 도구를 먼저 호출하여 해당 위원회의 정확한
       'committee_code'(HR_DEPT_CD)를 확인한 뒤, 이 'committee_code'로
       'get_committee_members'를 다시 호출하면 가장 정확한 결과를 얻을 수 있습니다.
    4. 일부 특별위원회는 OpenAPI에서 위원 명단 정보를 제공하지 않을 수 있습니다.

    - committee_code(HR_DEPT_CD)나 committee_name으로 조회 가능합니다.
    - 위원회명이 불분명하면 먼저 get_committee_list로 정확한 이름/코드를 찾으세요.
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
        # Cloud Run provides PORT, default to 8000 if neither is set
        default_port = os.getenv("PORT", "8000")
        port = int(os.getenv("MCP_PORT", default_port))
        path = os.getenv("MCP_PATH", "/mcp")

        logger.info(f"Starting AssemblyMCP with Streamable HTTP on {host}:{port}{path}")
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        # Default to stdio for local/desktop usage
        logger.info("Starting AssemblyMCP in stdio mode")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
