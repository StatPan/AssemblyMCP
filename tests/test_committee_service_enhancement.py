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
    # Mock INFO-200 response (No Data)

    mock_response = {
        "OCAJQ4001000LI18751": [
            {
                "head": [
                    {"status": "ok"},
                    {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}},
                ]
            },
            {"row": []},
        ]
    }

    mock_client.get_data = AsyncMock(return_value=mock_response)

    # Mock get_committee_list to return empty list (no suggestions)

    committee_service.get_committee_list = AsyncMock(return_value=[])

    result = await committee_service.get_committee_members(committee_name="없는위원회")

    assert isinstance(result, dict)

    assert "error" in result

    assert result["error"]["api_code"] == "INFO-200"

    assert "유효한 코드(HR_DEPT_CD)를 가진 위원회가 없습니다" in result["error"]["suggestion"]


@pytest.mark.asyncio
async def test_get_committee_members_info_200_with_suggestion(committee_service, mock_client):
    # Mock INFO-200 response

    mock_response = {
        "OCAJQ4001000LI18751": [
            {
                "head": [
                    {"status": "ok"},
                    {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}},
                ]
            },
            {"row": []},
        ]
    }

    mock_client.get_data = AsyncMock(return_value=mock_response)

    # Mock get_committee_list to return candidates

    mock_candidates = [
        Committee(
            HR_DEPT_CD="12345",
            COMMITTEE_NAME="유사위원회A",
            CMT_DIV_NM="상임",
            HG_NM="A",
        ),
        Committee(
            HR_DEPT_CD="67890",
            COMMITTEE_NAME="유사위원회B",
            CMT_DIV_NM="상임",
            HG_NM="B",
        ),
    ]

    committee_service.get_committee_list = AsyncMock(return_value=mock_candidates)

    result = await committee_service.get_committee_members(committee_name="유사위원회")

    assert isinstance(result, dict)

    assert "error" in result

    assert result["error"]["api_code"] == "INFO-200"

    suggestion = result["error"]["suggestion"]

    assert "다음과 같은 관련 위원회가 있습니다" in suggestion

    assert "유사위원회A(코드: 12345)" in suggestion

    assert "유사위원회B(코드: 67890)" in suggestion
