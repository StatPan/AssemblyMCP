"""MCP Server for Korean National Assembly API"""

import json
from datetime import date, datetime

from fastmcp import FastMCP

from assemblymcp.settings import settings
from src.client.assembly_api import AssemblyAPIClient
from src.models.bill import Bill
from src.services.discovery_service import DiscoveryService

# Initialize FastMCP server
mcp = FastMCP("AssemblyMCP")

# Initialize API Client globally to load specs once
client = AssemblyAPIClient(api_key=settings.assembly_api_key)

# Initialize Services
discovery_service = DiscoveryService(client)


@mcp.tool()
async def get_assembly_info() -> str:
    """
    Get basic information about the Korean National Assembly API.

    Returns:
        Information about available API endpoints and configuration status
    """
    api_key_status = "configured" if settings.assembly_api_key else "not configured"
    service_count = len(client.specs)
    return (
        f"Korean National Assembly Open API MCP Server\n"
        f"API Key: {api_key_status}\n"
        f"Available Services: {service_count}"
    )


@mcp.tool()
async def list_api_services(keyword: str = "") -> list[dict[str, str]]:
    """
    Search for available API services by keyword.

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
    except Exception as e:
        return f"Error calling API: {e}"


@mcp.tool(name="get_latest_bills")
async def get_latest_bills(size: int = 10, proposer_name: str | None = None) -> list[Bill]:
    """
    국회의원 발의법률안 데이터를 최신순으로 조회합니다.

    Args:
        size: 조회할 법률안의 최대 개수 (최대 100).
        proposer_name: 제안한 국회의원의 이름으로 필터링 (전체 이름 일치).

    Returns:
        조회된 법률안(Bill) 목록.
    """

    # 1. API 파라미터 준비
    service_id = "OK7XM1000938DS17215"
    params = {
        "pSize": min(size, 100),  # 최대 100건 제한
        "pIndex": 1,
    }

    if proposer_name:
        # API 문서에 따라 'PROPOSER' 파라미터로 필터링을 시도 (확인 필요)
        params["PROPOSER"] = proposer_name

    # 2. API 호출
    try:
        raw_data = await client.get_data(service_id=service_id, params=params)
    except Exception as e:
        # 오류가 발생하면 빈 목록이나 적절한 오류 메시지를 반환
        print(f"API 호출 실패: {e}")
        return []

    # 3. 데이터 정제 및 Bill 모델 변환
    bill_list = []

    # 임시 데이터 추출 로직 (추정) - 실제 API 응답 구조를 파악하면 업데이트 필요
    try:
        # API 서비스 ID와 동일한 키를 가진 리스트를 찾습니다.
        if isinstance(raw_data, dict):
            results = raw_data.get(service_id, [])
            if len(results) >= 1 and "row" in results[1]:
                rows = results[1]["row"]
                for row in rows:
                    # 날짜 형식 변환을 위한 임시 함수
                    def to_date(dt_str: str | None) -> date | None:
                        if dt_str and len(dt_str) == 8:
                            try:
                                return datetime.strptime(dt_str, "%Y%m%d").date()
                            except ValueError:
                                pass
                        return None

                    bill = Bill(
                        bill_no=row.get("BILL_NO", ""),
                        bill_name=row.get("BILL_NAME", ""),
                        propose_dt=to_date(row.get("PROPOSE_DT")),
                        proposer_gbn_nm=row.get("PROPOSER_GBN_NM", ""),
                        committee_dt=to_date(row.get("COMMITTEE_DT")),
                        proc_result_cd=row.get("PROC_RESULT_CD"),
                        link_url=row.get("LINK_URL"),
                    )
                    bill_list.append(bill)

    except Exception as e:
        print(f"데이터 정제 중 오류 발생: {e}")
        return []

    return bill_list


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
