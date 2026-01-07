from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from assembly_client.errors import AssemblyAPIError

from assemblymcp.server import (
    get_committee_info,
    get_member_info,
    get_member_voting_history,
    get_plenary_schedule,
    search_bills,
)
from assemblymcp.services import DiscoveryService, normalize_age, normalize_unit_cd


# 1. Normalization & Utility Tests
def test_unit_cd_normalization():
    assert normalize_unit_cd("22") == "100022"
    assert normalize_unit_cd(22) == "100022"
    assert normalize_unit_cd("22대") == "100022"
    assert normalize_unit_cd("100022") == "100022"
    assert normalize_unit_cd(None) == ""


def test_age_normalization():
    assert normalize_age("100022") == "22"
    assert normalize_age("22") == "22"
    assert normalize_age(22) == "22"
    assert normalize_age(None) == ""


@pytest.mark.asyncio
async def test_discovery_service_flexible_search():
    mock_client = MagicMock()
    mock_client.service_metadata = {
        "TEST_SERVICE": {"name": "위원회 위원 명단", "description": "설명", "category": "카테"}
    }
    service = DiscoveryService(mock_client)

    # 공백이 포함된 검색어로 공백 없는 서비스 찾기
    results = await service.list_services(keyword="위원회 명단")
    assert len(results) == 1
    assert results[0]["id"] == "TEST_SERVICE"

    # 대소문자 및 부분 일치
    results = await service.list_services(keyword="test")
    assert len(results) == 1


# 2. Retry Mechanism Test
@pytest.mark.asyncio
async def test_api_retry_logic():
    from assemblymcp.services import _get_data_with_retry

    mock_client = MagicMock()

    # 2번 실패 후 3번째에 성공하는 시나리오
    side_effects = [AssemblyAPIError("First Fail"), httpx.RequestError("Second Fail"), {"SUCCESS": "DATA"}]
    mock_client.get_data = AsyncMock(side_effect=side_effects)

    # 실제 호출
    result = await _get_data_with_retry(mock_client, "SERV_ID", {})

    assert result == {"SUCCESS": "DATA"}
    assert mock_client.get_data.call_count == 3


# 3. Server Tool Feedback Consistency Tests
@pytest.mark.asyncio
async def test_tool_empty_result_messages():
    # search_bills
    with patch("assemblymcp.server.bill_service") as mock_bill:
        mock_bill.search_bills = AsyncMock(return_value=[])
        res = await search_bills.fn(keyword="no_data")
        assert isinstance(res, str)
        assert "검색 조건에 맞는 의안이 없습니다" in res

    # get_plenary_schedule
    with patch("assemblymcp.server.meeting_service") as mock_meeting:
        mock_meeting.get_plenary_schedule = AsyncMock(return_value=[])
        res = await get_plenary_schedule.fn(unit_cd="22")
        assert isinstance(res, str)
        assert "본회의 일정이 없습니다" in res

    # get_member_info
    with patch("assemblymcp.server.member_service") as mock_member:
        mock_member.get_member_info = AsyncMock(return_value=[])
        res = await get_member_info.fn(name="유령의원")
        assert isinstance(res, str)
        assert "정보를 찾을 수 없습니다" in res


# 4. Specific Validation & Error Logic
@pytest.mark.asyncio
async def test_voting_history_validation():
    # 파라미터 둘 다 없을 때
    res = await get_member_voting_history.fn(name=None, bill_id=None)
    assert "반드시 입력해야 합니다" in res


@pytest.mark.asyncio
async def test_committee_info_error_handling():
    with patch("assemblymcp.server.committee_service") as mock_comm:
        mock_comm.get_committee_list = AsyncMock(return_value=[])
        # 서비스에서 에러 딕셔너리 리턴 시나리오
        mock_comm.get_committee_members = AsyncMock(
            return_value={"error": {"suggestion": "추천 검색어: 법제사법위원회"}}
        )

        res = await get_committee_info.fn(committee_name="잘못된위위")
        assert "추천 검색어" in res
