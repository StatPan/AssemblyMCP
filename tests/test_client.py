import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from assemblymcp.client import AssemblyAPIClient, AssemblyAPIError

SAMPLE_SPEC = {"OPENSRVAPI": [{"row": [{"INF_ID": "TEST_ID", "INF_NM": "Test Service"}]}]}


@pytest.fixture
def mock_env():
    with patch.dict("os.environ", {"ASSEMBLY_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_specs():
    # Mock Path.glob to return a list of mock paths
    mock_path = MagicMock(spec=Path)
    mock_path.__str__.return_value = "specs/all_apis_p1.json"

    with (
        patch("pathlib.Path.glob", return_value=[mock_path]),
        patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_SPEC))),
        patch("pathlib.Path.exists", return_value=True),
    ):
        yield


@pytest.mark.asyncio
async def test_client_init(mock_env, mock_specs):
    client = AssemblyAPIClient()
    assert client.api_key == "test_key"
    # The loading logic relies on Path(__file__).parent...
    # Since we mocked glob and open, it should load TEST_ID if logic is correct.
    # But we need to ensure _load_specs actually runs and finds the file.
    # The current _load_specs uses Path(__file__).parent.parent.parent / "specs"
    # We mocked Path.exists and glob, so it should work.
    assert "TEST_ID" in client.specs


@pytest.mark.asyncio
async def test_get_data_success(mock_env, mock_specs):
    client = AssemblyAPIClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "test_endpoint": [
            {"head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}]},
            {"row": [{"data": "value"}]},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    # Mock get_endpoint to return a test endpoint
    client.get_endpoint = AsyncMock(return_value="test_endpoint")

    # Mock the async client.get method
    client.client.get = AsyncMock(return_value=mock_response)

    data = await client.get_data("TEST_ID")
    assert data["test_endpoint"][1]["row"][0]["data"] == "value"
    client.client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_data_error(mock_env, mock_specs):
    client = AssemblyAPIClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "test_endpoint": [{"head": [{"RESULT": {"CODE": "INFO-300", "MESSAGE": "Error"}}]}]
    }
    mock_response.raise_for_status = MagicMock()

    # Mock get_endpoint
    client.get_endpoint = AsyncMock(return_value="test_endpoint")
    client.client.get = AsyncMock(return_value=mock_response)

    with pytest.raises(AssemblyAPIError) as exc:
        await client.get_data("TEST_ID")
    assert "INFO-300" in str(exc.value)
