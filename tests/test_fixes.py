import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from assembly_client.api import AssemblyAPIClient

from assemblymcp.initialization import ensure_master_list
from assemblymcp.services import BillService, MemberService


@pytest.fixture
def mock_client(tmp_path):
    client = MagicMock(spec=AssemblyAPIClient)
    client.spec_parser = MagicMock()
    # Use a temporary directory for cache
    client.spec_parser.cache_dir = tmp_path
    client.api_key = "test_key"
    client.client = AsyncMock()
    client.BASE_URL = "https://open.assembly.go.kr/portal/openapi"
    return client


@pytest.mark.asyncio
async def test_ensure_master_list_downloads_if_missing(mock_client):
    """Test that ensure_master_list downloads the master list if it doesn't exist."""
    master_file = mock_client.spec_parser.cache_dir / "all_apis.json"
    assert not master_file.exists()

    # Mock API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "OPENSRVAPI": [
            {"head": [{"status": "OK"}]},
            {"row": [{"INF_ID": "TEST_ID", "INF_NM": "Test Service"}]},
        ]
    }
    mock_client.client.get.return_value = mock_response

    await ensure_master_list(mock_client)

    # Verify file created
    assert master_file.exists()

    # Verify content
    with open(master_file) as f:
        data = json.load(f)
        assert "OPENSRVAPI" in data
        assert data["OPENSRVAPI"][1]["row"][0]["INF_ID"] == "TEST_ID"

    # Verify API call
    mock_client.client.get.assert_called_once()
    args, kwargs = mock_client.client.get.call_args
    assert "OPENSRVAPI" in args[0]


@pytest.mark.asyncio
async def test_ensure_master_list_skips_if_exists(mock_client):
    """Test that ensure_master_list skips download if file exists."""
    master_file = mock_client.spec_parser.cache_dir / "all_apis.json"
    master_file.write_text("{}")

    await ensure_master_list(mock_client)

    # Verify API NOT called
    mock_client.client.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_bill_details_numeric_id_bypass(mock_client):
    """Test that get_bill_details bypasses search for numeric IDs."""
    bill_service = BillService(mock_client)

    # Mock get_bill_info to return empty (simulating search failure)
    bill_service.get_bill_info = AsyncMock(return_value=[])

    # Mock get_data for detail call
    detail_response = {
        "OS46YD0012559515463": [
            {"head": []},
            {"row": [{"MAIN_CNTS": "Summary", "RSON_CONT": "Reason"}]},
        ]
    }
    mock_client.get_data = AsyncMock(return_value=detail_response)

    numeric_id = "2214308"
    detail = await bill_service.get_bill_details(numeric_id)

    assert detail is not None
    assert detail.bill_id == numeric_id
    assert detail.summary == "Summary"

    # Verify get_data called with BILL_NO
    mock_client.get_data.assert_called()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["params"]["BILL_NO"] == numeric_id


@pytest.mark.asyncio
async def test_member_service_id_is_correct(mock_client):
    """Test that MemberService uses the correct Service ID."""
    member_service = MemberService(mock_client)
    assert member_service.MEMBER_INFO_ID == "NWVRRE001000000001"
