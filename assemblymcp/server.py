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
from assemblymcp.smart import SmartService

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
mcp.add_middleware(CachingMiddleware())  # Was innermost
mcp.add_middleware(InitializationMiddleware(client))
mcp.add_middleware(LoggingMiddleware())


# Initialize Services
if client:
    discovery_service = DiscoveryService(client)
    bill_service = BillService(client)
    member_service = MemberService(client)
    meeting_service = MeetingService(client)
    committee_service = CommitteeService(client)
    smart_service = SmartService(bill_service, meeting_service, member_service)
else:
    discovery_service = None
    bill_service = None
    member_service = None
    meeting_service = None
    committee_service = None
    smart_service = None

ServiceT = TypeVar("ServiceT")


def _require_service[ServiceT](service: ServiceT | None) -> ServiceT:
    """Ensure the API client and requested service are available."""
    if service is None:
        raise RuntimeError(
            "Assembly API client is not ready. Set the ASSEMBLY_API_KEY environment variable and restart the server."
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
            "AssemblyMCP는 LLM의 사용 편의성을 극대화하는 지능형 기능을 제공합니다.\n\n"
            "👉 핵심 워크플로우:\n"
            "1) 종합 분석: analyze_legislative_issue('주제') -> 법안, 회의록, 의원 통합 리포트\n"
            "2) 의원 분석: get_representative_report('의원명') -> 인적사항, 발의법안, 경력, 투표이력 종합 리포트\n"
            "3) 투표 분석: get_bill_voting_results('의안ID') -> 본회의 표결 결과 및 정당별 찬반 경향\n"
            "4) 전문 데이터: get_legislative_reports('주제') -> NABO(예산정책처) 전문 분석 보고서 및 뉴스 링크 제공\n"
            "5) 위원회 현황: get_committee_work_summary('위원회명') -> 해당 위원회의 계류 법안과 보고서 통합 뷰\n"
            "6) 의안 탐색: search_bills() → get_bill_details() → get_bill_history() (타임라인/연혁)\n\n"
            "👉 지능형 도구 (LLM을 위한 인프라):\n"
            "- get_api_code_guide: UNIT_CD(대수), PROC_STATUS(처리상태) 등 복잡한 코드값 사전 제공\n"
            "- 자동 보정: call_api_raw 호출 시 UNIT_CD='22' 등을 입력해도 "
            "서버가 자동으로 '100022'로 보정하여 호출합니다.\n"
            "- list_api_services → get_api_spec → call_api_raw 조합으로 어떤 정보든 조회 가능합니다.\n\n"
            "팁: 특정 주제에 맞는 서비스가 안 보이면 키워드를 바꿔 여러 번 검색하고, "
            "데이터가 부족하다고 섣불리 결론 내리지 마세요."
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
async def list_api_services(keyword: str = "") -> list[dict[str, str]] | str:
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
    results = await service.list_services(keyword)
    if not results and keyword:
        return f"키워드 '{keyword}'에 대한 검색 결과가 없습니다. 공백을 제거하거나 다른 핵심 키워드로 검색해보세요."
    return results


@mcp.tool()
async def call_api_raw(service_id: str, params: str = "{}") -> str:
    """
    모든 국회 OpenAPI를 직접 호출하는 만능 백도어입니다.

    - "해당 기능이 없다"는 답을 피하기 위해 항상 이 경로를 고려하세요.
    - 절차: list_api_services로 ID 찾기 → get_api_spec로 파라미터 확인 → 여기서 호출.
    - 응답을 받은 뒤, 필요한 경우 다른 고수준 툴(예: get_member_info, get_meeting_records)로
      후속 검색을 연쇄 호출해 답을 완성하세요.

    [주의] 이 툴은 입력값을 변환하지 않고 그대로 전송합니다.
    - 특히 'UNIT_CD'(대수) 파라미터는 반드시 '1000xx' 형식을 사용해야 합니다.
      (예: 22대 국회 -> "100022", 21대 국회 -> "100021")
      단순히 "22"라고 입력하면 데이터가 조회되지 않습니다.

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
async def search_bills(
    keyword: str | None = None,
    bill_id: str | None = None,
    proposer: str | None = None,
    age: str = "22",
    propose_dt: str | None = None,
    proc_status: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]] | str:
    """
    의안을 검색하거나 목록을 조회합니다. (통합 검색 도구)

    기능:
    1. 키워드 검색: 'keyword'만 입력 (예: "인공지능")
    2. 필터 검색: 'proposer'(발의자), 'bill_id', 'proc_status' 등 조합
    3. 최신 목록: 파라미터 없이 호출하면 현재 대수의 최신 발의 의안 반환
    4. 스마트 검색: 키워드 검색 시 현재 대수(22대) 결과가 없으면 이전 대수(21대) 자동 검색

    Args:
        keyword: 검색어 (의안명).
        bill_id: 의안 고유 ID 또는 의안 번호.
        proposer: 제안자(의원명 등).
        age: 국회 대수 (기본 "22").
        propose_dt: 제안일자 (YYYYMMDD).
        proc_status: 처리상태 코드.
        page: 페이지 번호 (기본 1).
        limit: 최대 결과 수 (기본 10).

    Returns:
        검색된 의안 목록.
    """
    service = _require_service(bill_service)

    # If only keyword is provided, use the smart search logic
    if keyword and not any([bill_id, proposer, propose_dt, proc_status]) and age == "22":
        bills = await service.search_bills(keyword, page=page, limit=limit)
    # If no filters provided, get recent bills
    elif not any([keyword, bill_id, proposer, propose_dt, proc_status]):
        bills = await service.get_recent_bills(page=page, limit=limit)
    # Otherwise, use general filtering
    else:
        bills = await service.get_bill_info(
            age=age,
            bill_id=bill_id,
            bill_name=keyword,
            proposer=proposer,
            propose_dt=propose_dt,
            proc_status=proc_status,
            page=page,
            limit=limit,
        )

    if not bills:
        msg = "검색 조건에 맞는 의안이 없습니다."
        if keyword:
            msg += f" (키워드: {keyword})"
        return msg

    return [bill.model_dump(exclude_none=True) for bill in bills]


@mcp.tool(output_schema=bill_detail_output_schema())
async def get_bill_details(bill_id: str, age: str | None = None) -> dict[str, Any] | str:
    """
    특정 의안의 상세 정보를 조회합니다.
    의안의 요약(MAJOR_CONTENT)과 제안 이유(PROPOSE_REASON)를 포함합니다.

    사용법:
    1. 'search_bills'로 의안 검색 후 'BILL_ID' 또는 'BILL_NO' 확인
    2. 이 툴에 ID를 전달하여 상세 내용 조회

    Args:
        bill_id: 의안 ID (예: 'PRC_...') 또는 의안 번호 (예: '2200001').
        age: 선택적 대수 (예: "22").

    Returns:
        상세 정보가 포함된 의안 객체.
    """
    service = _require_service(bill_service)
    details = await service.get_bill_details(bill_id, age=age)
    if not details:
        return f"의안 ID/번호 '{bill_id}'에 대한 상세 정보를 찾을 수 없습니다."
    return details.model_dump(exclude_none=True)


@mcp.tool()
async def get_bill_history(bill_id: str) -> list[dict[str, Any]]:
    """
    특정 의안의 발의부터 현재까지의 모든 주요 이력(회의 포함)을 날짜순으로 통합하여 조회합니다.
    타임라인 생성이나 연혁 분석에 매우 유용합니다.

    Args:
        bill_id: 의안 ID (예: 'PRC_...') 또는 의안 번호 (예: '2200001').
    """
    service = _require_service(smart_service)
    return await service.get_bill_history(bill_id)


@mcp.tool()
async def analyze_legislative_issue(topic: str, limit: int = 5) -> dict[str, Any]:
    """
    특정 주제(이슈)에 대한 종합적인 입법 현황 분석 리포트를 생성합니다.
    이 도구는 관련 법안 검색, 주요 법안의 상세 내용, 관련 위원회 회의록,
    그리고 해당 주제를 주도하는 주요 국회의원 정보를 한 번에 통합하여 제공합니다.

    Args:
        topic: 분석할 입법 주제 또는 키워드 (예: "인공지능", "저출산").
        limit: 검색할 관련 법안 수 (기본 5).

    Returns:
        종합 분석 리포트 데이터.
    """
    service = _require_service(smart_service)
    return await service.analyze_legislative_issue(topic, limit=limit)


@mcp.tool()
async def get_legislative_reports(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    특정 주제나 법안과 관련된 국회 전문 보고서(NABO Focus 등) 및 뉴스를 조회합니다.
    단순 법안 정보를 넘어 전문가의 분석 시각을 제공할 때 유용합니다.

    Args:
        keyword: 검색 키워드 (예: "종합부동산세", "인공지능").
        limit: 검색 결과 수 (기본 5).
    """
    service = _require_service(smart_service)
    reports = await service.get_legislative_reports(keyword, limit=limit)
    return [r.model_dump(exclude_none=True) for r in reports]


@mcp.tool()
async def get_committee_work_summary(committee_name: str) -> dict[str, Any]:
    """
    특정 위원회의 현재 활동 현황(계류 의안, 관련 보고서 등)을 한 번에 조회합니다.
    엔티티 간의 연관 데이터를 매핑하여 객관적인 정보를 제공합니다.

    Args:
        committee_name: 위원회명 (예: "법제사법위원회", "환경노동위원회").
    """
    service = _require_service(smart_service)
    summary = await service.get_committee_work_summary(committee_name)
    return summary.model_dump(exclude_none=True)


@mcp.tool()
async def get_committee_voting_stats(committee_name: str) -> dict[str, Any]:
    """
    특정 위원회가 처리한 가결 법안들의 본회의 찬성률 통계를 집계하여 반환합니다.
    해당 위원회의 법안들이 본회의에서 어떤 수치로 통과되었는지 팩트 기반으로 제공합니다.

    Args:
        committee_name: 위원회명 (예: "법제사법위원회", "기획재정위원회").
    """
    service = _require_service(smart_service)
    stats = await service.get_committee_voting_stats(committee_name)
    return stats.model_dump(exclude_none=True)


@mcp.tool()
async def get_topic_voting_stats(keyword: str, limit: int = 10) -> dict[str, Any]:
    """
    특정 키워드가 포함된 법안들의 본회의 투표 찬성률 통계를 집계하여 반환합니다.
    단순 키워드 매칭을 통해 검색된 법안들의 수치적 합계 데이터만 제공합니다.

    Args:
        keyword: 검색 키워드 (예: "인공지능", "종합부동산세").
        limit: 집계할 최대 법안 수 (기본 10).
    """
    service = _require_service(smart_service)
    stats = await service.get_topic_voting_stats(keyword, limit=limit)
    return stats.model_dump(exclude_none=True)


@mcp.tool()
async def get_api_code_guide() -> dict[str, Any]:
    """
    국회 API에서 공통으로 사용되는 코드값(대수, 처리상태 등) 가이드를 반환합니다.
    LLM이 call_api_raw를 호출하기 전 파라미터 값을 결정할 때 참고하세요.
    """
    return {
        "UNIT_CD (국회 대수)": {
            "description": "국회 대수를 나타내는 6자리 코드",
            "mapping": {"22대": "100022", "21대": "100021", "20대": "100020"},
            "note": "AssemblyMCP가 '22' 같은 입력을 자동으로 '100022'로 보정해줍니다.",
        },
        "PROC_RESULT_CD (의안 처리상태)": {
            "description": "의안의 현재 처리 단계 또는 결과 코드",
            "codes": {
                "1000": "접수",
                "2000": "위원회 심사",
                "3000": "본회의 심의",
                "4000": "의결 (가결/수정가결 등)",
                "5000": "폐기/철회",
            },
        },
        "Common_Parameters": {
            "pIndex": "페이지 번호 (기본: 1)",
            "pSize": "한 페이지당 결과 수 (기본: 10, 최대: 100)",
            "Type": "응답 형식 (json 권장)",
        },
    }


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
async def search_meetings(
    bill_id: str | None = None,
    committee_name: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]] | str:
    """
    위원회 회의 정보를 검색합니다.

    Args:
        bill_id: 특정 의안과 관련된 회의를 찾을 때 사용 (예: '2100001').
        committee_name: 위원회명 (예: "법제사법위원회").
        date_start: 시작일 (YYYY-MM-DD).
        date_end: 종료일 (YYYY-MM-DD).
        page: 페이지 번호 (기본 1).
        limit: 최대 결과 수 (기본 10).

    Returns:
        회의록 및 일정 목록.
    """
    service = _require_service(meeting_service)

    if bill_id:
        records = await service.get_meeting_records(bill_id)
        if not records:
            return f"의안 ID '{bill_id}'와 관련된 회의 기록이 없습니다."
        return records

    results = await service.search_meetings(
        committee_name=committee_name,
        date_start=date_start,
        date_end=date_end,
        page=page,
        limit=limit,
    )
    if not results:
        return "검색 조건에 맞는 회의 일정이 없습니다."
    return results


@mcp.tool()
async def get_plenary_schedule(
    unit_cd: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]] | str:
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
    results = await service.get_plenary_schedule(unit_cd=unit_cd, page=page, limit=limit)
    if not results:
        return f"대수(unit_cd) '{unit_cd or '전체'}'에 대한 본회의 일정이 없습니다."
    return results


@mcp.tool()
async def get_committee_info(
    committee_name: str | None = None,
    committee_code: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict[str, Any]:
    """
    위원회 목록을 조회하거나 특정 위원회의 상세 정보(위원 명단 포함)를 가져옵니다.

    Args:
        committee_name: 위원회명 (예: "법제사법위원회").
        committee_code: 위원회 코드 (HR_DEPT_CD).
        page: 페이지 번호 (기본 1).
        limit: 최대 결과 수 (기본 50).

    Returns:
        위원회 목록 또는 특정 위원회 상세 정보.
    """
    service = _require_service(committee_service)

    # If specific committee is requested
    if committee_name or committee_code:
        # Get basic info
        committees = await service.get_committee_list(committee_name)
        # If code was provided, filter strictly
        if committee_code:
            committees = [c for c in committees if committee_code == c.HR_DEPT_CD]

        # Get members
        members = await service.get_committee_members(
            committee_code=committee_code,
            committee_name=committee_name,
            page=page,
            limit=limit,
        )

        return {
            "committee": [c.model_dump(exclude_none=True) for c in committees],
            "members": members,
        }

    # Otherwise return the full list
    committees = await service.get_committee_list()
    return {"committees": [c.model_dump(exclude_none=True) for c in committees]}


@mcp.tool()
async def get_representative_report(member_name: str) -> dict[str, Any]:
    """
    특정 국회의원의 종합 의정활동 리포트를 생성합니다.
    인적사항, 최근 대표 발의 법안, 위원회 경력, 최근 본회의 투표 이력을 한 번에 제공합니다.

    Args:
        member_name: 국회의원 성명 (예: "추경호").
    """
    service = _require_service(smart_service)
    report = await service.get_representative_report(member_name)
    return report.model_dump(exclude_none=True)


@mcp.tool()
async def get_bill_voting_results(bill_id: str) -> dict[str, Any]:
    """
    특정 의안에 대한 본회의 표결 결과(찬성, 반대, 기권 수)와 정당별 투표 경향을 조회합니다.

    Args:
        bill_id: 의안 ID (예: 'PRC_...').
    """
    service = _require_service(smart_service)
    return await service.get_bill_voting_results(bill_id)


@mcp.tool()
async def analyze_voting_trends(topic: str) -> dict[str, Any]:
    """
    특정 주제(키워드)와 관련된 법안들의 본회의 투표 경향을 분석합니다.
    최근 관련 법안들의 가결 여부와 찬반 통계를 요약하여 제공합니다.

    Args:
        topic: 분석할 주제 또는 키워드 (예: "종합부동산세", "간호법").
    """
    service = _require_service(smart_service)
    return await service.analyze_voting_trends(topic)


@mcp.tool()
async def get_member_voting_history(
    name: str | None = None,
    bill_id: str | None = None,
    age: str = "22",
    page: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    국회의원 개인의 본회의 표결 기록 또는 특정 의안의 개별 의원 표결 현황을 조회합니다.

    Args:
        name: 의원 성명 (특정 의원의 이력을 볼 때 사용).
        bill_id: 의안 ID (특정 의안에 누가 어떻게 투표했는지 볼 때 사용).
        age: 국회 대수 (기본 "22").
        page: 페이지 번호.
        limit: 결과 수 (최대 100).
    """
    service = _require_service(bill_service)
    records = await service.get_member_voting_history(name=name, bill_id=bill_id, age=age, page=page, limit=limit)
    return [r.model_dump(exclude_none=True) for r in records]


@mcp.tool()
async def get_member_committee_careers(name: str) -> list[dict[str, Any]]:
    """
    특정 국회의원의 과거 및 현재 위원회 활동 경력을 조회합니다.

    Args:
        name: 의원 성명.
    """
    service = _require_service(member_service)
    careers = await service.get_member_committee_careers(name)
    return [c.model_dump(exclude_none=True) for c in careers]


def main():
    """Run the MCP server"""
    sys.stdout.reconfigure(line_buffering=True)
    # Validate settings on startup (but don't fail if API key is missing yet)
    if not settings.assembly_api_key:
        logger.warning("ASSEMBLY_API_KEY is not configured. The server will run but tools will fail.")

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
