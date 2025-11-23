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
async def test_get_committee_list(committee_service, mock_client):
    # Mock API response
    mock_response = {
        "O2Q4ZT001004PV11014": [
            {
                "head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}],
                "row": [
                    {
                        "HR_DEPT_CD": "9700008",
                        "COMMITTEE_NAME": "법제사법위원회",
                        "CMT_DIV_NM": "상임위원회",
                        "HG_NM": "박광온",
                        "CURR_CNT": "18",
                        "LIMIT_CNT": "18",
                    },
                    {
                        "HR_DEPT_CD": "9700009",
                        "COMMITTEE_NAME": "정무위원회",
                        "CMT_DIV_NM": "상임위원회",
                        "HG_NM": "백혜련",
                        "CURR_CNT": "24",
                        "LIMIT_CNT": "24",
                    },
                ],
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    committees = await committee_service.get_committee_list()

    assert len(committees) == 2
    assert isinstance(committees[0], Committee)
    assert committees[0].committee_code == "9700008"
    assert committees[0].committee_name == "법제사법위원회"
    assert committees[0].chairperson == "박광온"
    assert committees[0].member_count == 18

    # Verify API call parameters
    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["service_id"] == "O2Q4ZT001004PV11014"
    assert call_args.kwargs["params"] == {}


@pytest.mark.asyncio
async def test_get_committee_list_filter(committee_service, mock_client):
    mock_client.get_data = AsyncMock(return_value={})

    await committee_service.get_committee_list(committee_name="법제사법위원회")

    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["params"]["COMMITTEE_NAME"] == "법제사법위원회"
