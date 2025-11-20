"""MCP Server for Korean National Assembly API"""

import json
import logging

from fastmcp import FastMCP

from assemblymcp.client import AssemblyAPIClient, AssemblyAPIError
from assemblymcp.models import Bill
from assemblymcp.services import BillService, DiscoveryService
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
    except AssemblyAPIError as e:
        logger.error(f"API error calling service '{service_id}': {e}")
        return f"API Error: {e}"
    except Exception:
        logger.exception(f"Unexpected error calling API service '{service_id}'")
        return "An unexpected error occurred."


@mcp.tool()
async def get_bill_info(
    age: str,
    bill_id: str | None = None,
    bill_name: str | None = None,
    propose_dt: str | None = None,
    proc_status: str | None = None,
    limit: int = 10,
) -> list[Bill]:
    """
    Search for legislative bills (의안) by ID, name, proposal date, or processing status.
    This function integrates and abstracts multiple Bill APIs into a unified result.

    Args:
        age: 대 (AGE). REQUIRED. 조회할 국회의 대수 (예: '21').
        bill_id: 의안ID (BILL_ID/BILL_NO). 의안의 고유 식별자.
        bill_name: 의안명 (BILL_NAME). 의안의 전체 이름.
        propose_dt: 제안일자 (PROPOSE_DT). 의안이 발의된 날짜 (YYYYMMDD 형식).
        proc_status: 처리상태 (PROC_STATUS). 의안의 현재 처리 단계 (예: 위원회 심사 등).
        limit: 조회할 법률안의 최대 개수 (최대 100).

    Returns:
        조회된 법률안(Bill) 목록.
    """
    return await bill_service.get_bill_info(
        age=age,
        bill_id=bill_id,
        bill_name=bill_name,
        propose_dt=propose_dt,
        proc_status=proc_status,
        limit=limit,
    )


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
