from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import DiscoveryService, MeetingService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    # Setup async mock for get_data
    mock.get_data = AsyncMock(return_value={"row": []})
    return mock


@pytest.fixture
def meeting_service(mock_client):
    return MeetingService(mock_client)


@pytest.fixture
def discovery_service(mock_client):
    return DiscoveryService(mock_client)


@pytest.mark.asyncio
async def test_get_plenary_schedule_auto_formatting(meeting_service, mock_client):
    """Verify that '22' is converted to '100022' in get_plenary_schedule."""
    await meeting_service.get_plenary_schedule(unit_cd="22")

    call_args = mock_client.get_data.call_args
    assert call_args is not None
    params = call_args.kwargs["params"]
    assert params["UNIT_CD"] == "100022"


@pytest.mark.asyncio
async def test_get_plenary_schedule_auto_formatting_with_text(meeting_service, mock_client):
    """Verify that '22대' is converted to '100022' in get_plenary_schedule."""
    await meeting_service.get_plenary_schedule(unit_cd="22대")

    call_args = mock_client.get_data.call_args
    assert call_args is not None
    params = call_args.kwargs["params"]
    assert params["UNIT_CD"] == "100022"


@pytest.mark.asyncio
async def test_get_plenary_schedule_no_formatting_for_full_code(meeting_service, mock_client):
    """Verify that '100022' remains '100022' in get_plenary_schedule."""
    await meeting_service.get_plenary_schedule(unit_cd="100022")

    call_args = mock_client.get_data.call_args
    assert call_args is not None
    params = call_args.kwargs["params"]
    assert params["UNIT_CD"] == "100022"


@pytest.mark.asyncio
async def test_call_raw_no_formatting(discovery_service, mock_client):
    """Verify that call_raw does NOT format UNIT_CD."""
    await discovery_service.call_raw(service_id_or_name="TEST_ID", params={"UNIT_CD": "22"})

    call_args = mock_client.get_data.call_args
    assert call_args is not None
    params = call_args.kwargs["params"]
    # Should remain exactly "22"
    assert params["UNIT_CD"] == "22"
