from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import DiscoveryService

# Sample specs for testing
SAMPLE_SPECS = {
    "TEST_ID_1": {
        "INF_ID": "TEST_ID_1",
        "INF_NM": "Meeting Records",
        "INF_EXP": "Records of assembly meetings",
        "CATE_NM": "Activity",
    },
    "TEST_ID_2": {
        "INF_ID": "TEST_ID_2",
        "INF_NM": "Member Info",
        "INF_EXP": "Information about members",
        "CATE_NM": "Member",
    },
}


@pytest.fixture
def mock_client():
    mock = MagicMock()
    mock.specs = SAMPLE_SPECS
    return mock


@pytest.fixture
def discovery_service(mock_client):
    return DiscoveryService(mock_client)


@pytest.mark.asyncio
async def test_list_services_all(discovery_service):
    results = await discovery_service.list_services()
    assert len(results) == 2
    assert results[0]["name"] == "Meeting Records"
    assert results[1]["name"] == "Member Info"


@pytest.mark.asyncio
async def test_list_services_filter(discovery_service):
    results = await discovery_service.list_services(keyword="Member")
    assert len(results) == 1
    assert results[0]["id"] == "TEST_ID_2"


@pytest.mark.asyncio
async def test_call_raw_success(discovery_service, mock_client):
    mock_client.get_data = AsyncMock(return_value={"result": "success"})

    result = await discovery_service.call_raw("TEST_ID_1", params={"pSize": 5})

    mock_client.get_data.assert_called_once_with(service_id="TEST_ID_1", params={"pSize": 5})
    assert result == {"result": "success"}
