from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import MeetingService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def meeting_service(mock_client):
    return MeetingService(mock_client)


@pytest.mark.asyncio
async def test_search_meetings_by_committee(meeting_service, mock_client):
    # Mock API response
    mock_response = {
        "OR137O001023MZ19321": [
            {
                "head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}],
                "row": [
                    {
                        "CONF_DATE": "20241120",
                        "COMM_NAME": "법제사법위원회",
                        "TITLE": "제410회국회(정기회) 제10차 법제사법위원회",
                    },
                    {
                        "CONF_DATE": "20241115",
                        "COMM_NAME": "법제사법위원회",
                        "TITLE": "제410회국회(정기회) 제9차 법제사법위원회",
                    },
                ],
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    meetings = await meeting_service.search_meetings(committee_name="법제사법위원회")

    assert len(meetings) == 2
    assert meetings[0]["COMM_NAME"] == "법제사법위원회"
    assert meetings[0]["CONF_DATE"] == "20241120"

    # Verify API call
    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["service_id"] == "OR137O001023MZ19321"
    assert call_args.kwargs["params"]["COMM_NAME"] == "법제사법위원회"


@pytest.mark.asyncio
async def test_search_meetings_by_date_range(meeting_service, mock_client):
    # Mock API response with dates outside range
    mock_response = {
        "OR137O001023MZ19321": [
            {
                "head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}],
                "row": [
                    {
                        "CONF_DATE": "20241120",
                        "COMM_NAME": "법제사법위원회",
                    },
                    {
                        "CONF_DATE": "20241110",  # Should be filtered out
                        "COMM_NAME": "법제사법위원회",
                    },
                ],
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    # Search for meetings after 2024-11-15
    meetings = await meeting_service.search_meetings(date_start="2024-11-15")

    assert len(meetings) == 1
    assert meetings[0]["CONF_DATE"] == "20241120"

    # Verify API call
    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    # Check that date_start was passed to params (formatted)
    assert call_args.kwargs["params"]["CONF_DATE"] == "20241115"
