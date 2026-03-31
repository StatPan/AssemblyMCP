from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.models import Committee
from assemblymcp.services import CommitteeService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def committee_service(mock_client):
    return CommitteeService(mock_client)


@pytest.mark.asyncio
async def test_get_committee_members_info_200_no_suggestion(committee_service, mock_client):
    """Empty result with no candidate committees → generic suggestion returned."""
    mock_client.get_data = AsyncMock(return_value=[])
    committee_service.get_committee_list = AsyncMock(return_value=[])

    result = await committee_service.get_committee_members(committee_name="없는위원회")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"]["error_type"] == "DATA_NOT_FOUND"
    assert "get_committee_list" in result["error"]["suggestion"]


@pytest.mark.asyncio
async def test_get_committee_members_info_200_with_suggestion(committee_service, mock_client):
    """Empty result with candidate committees → suggestion includes committee codes."""
    mock_client.get_data = AsyncMock(return_value=[])

    mock_candidates = [
        Committee(HR_DEPT_CD="12345", COMMITTEE_NAME="유사위원회A", CMT_DIV_NM="상임", HG_NM="A"),
        Committee(HR_DEPT_CD="67890", COMMITTEE_NAME="유사위원회B", CMT_DIV_NM="상임", HG_NM="B"),
    ]
    committee_service.get_committee_list = AsyncMock(return_value=mock_candidates)

    result = await committee_service.get_committee_members(committee_name="유사위원회")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"]["error_type"] == "DATA_NOT_FOUND"
    suggestion = result["error"]["suggestion"]
    assert "다음과 같은 관련 위원회가 있습니다" in suggestion
    assert "유사위원회A(코드: 12345)" in suggestion
    assert "유사위원회B(코드: 67890)" in suggestion
