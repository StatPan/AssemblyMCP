from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.config import settings
from assemblymcp.services import MeetingService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def meeting_service(mock_client):
    return MeetingService(mock_client)


@pytest.mark.asyncio
async def test_search_meetings_uses_schedule_api(meeting_service, mock_client):
    """
    Test that search_meetings uses the Schedule API and filters by date correctly.
    """
    # Mock Schedule API response
    mock_response = {
        "nttmdfdcaakvibdar": [
            {
                "head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}],
                "row": [
                    {
                        "MEETING_DATE": "2025-12-29",
                        "TITLE": "전체회의",
                        "COMMITTEE_NAME": "법제사법위원회",
                        "UNIT_CD": "100022",
                    },
                    {
                        "MEETING_DATE": "2025-12-01",  # Out of range
                        "TITLE": "전체회의",
                        "COMMITTEE_NAME": "법제사법위원회",
                        "UNIT_CD": "100022",
                    },
                ],
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    # Configure settings default age
    settings.default_assembly_age = "22"

    # Search range: 2025-12-20 to 2025-12-30
    results = await meeting_service.search_meetings(
        committee_name="법제사법위원회", date_start="2025-12-20", date_end="2025-12-30"
    )

    # 1. Verify API Call
    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["service_id_or_name"] == "O27DU0000960M511942"
    assert call_args.kwargs["params"]["COMMITTEE_NAME"] == "법제사법위원회"
    assert call_args.kwargs["params"]["UNIT_CD"] == "100022"  # Converted

    # 2. Verify Filtering
    assert len(results) == 1
    assert results[0]["MEETING_DATE"] == "2025-12-29"
    # Verify field remapping
    assert results[0]["CONF_DATE"] == "20251229"
    assert results[0]["CONF_TITLE"] == "전체회의"


@pytest.mark.asyncio
async def test_unit_cd_conversion(meeting_service):
    """Test the heuristic conversion of assembly age to UNIT_CD."""
    assert meeting_service._convert_unit_cd("22") == "100022"
    assert meeting_service._convert_unit_cd(22) == "100022"
    assert meeting_service._convert_unit_cd("21") == "100021"
    # If already converted or unknown format
    assert meeting_service._convert_unit_cd("100022") == "100022"
    assert meeting_service._convert_unit_cd("Cheolsu") == "Cheolsu"
