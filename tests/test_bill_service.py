from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.models import Bill
from assemblymcp.services import BillService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def bill_service(mock_client):
    return BillService(mock_client)


@pytest.mark.asyncio
async def test_get_bill_info_success(bill_service, mock_client):
    mock_client.get_data = AsyncMock(
        return_value=[
            {
                "BILL_ID": "PRC_T2T3T4T5T6T7T8T9",
                "BILL_NO": "2100001",
                "BILL_NAME": "Test Bill",
                "PROPOSER": "Test Proposer",
                "PROPOSER_KIND": "Member",
                "PROC_RESULT_NM": "Passed",
                "CURR_COMMITTEE": "Legislation",
                "PROPOSE_DT": "20200101",
                "COMMITTEE_DT": "20200102",
                "PROC_DT": "20200103",
                "LINK_URL": "http://test.com",
            }
        ]
    )

    bills = await bill_service.get_bill_info(age="21", limit=1)

    assert len(bills) == 1
    assert isinstance(bills[0], Bill)
    assert bills[0].BILL_ID == "PRC_T2T3T4T5T6T7T8T9"
    assert bills[0].BILL_NO == "2100001"
    assert bills[0].BILL_NAME == "Test Bill"
    assert bills[0].PROPOSER == "Test Proposer"

    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["service_id_or_name"] == "O4K6HM0012064I15889"
    assert call_args.kwargs["params"]["AGE"] == "21"
    assert call_args.kwargs["params"]["pSize"] == 1

    mock_client.get_data = AsyncMock(return_value=[])
    bills = await bill_service.get_bill_info(age="21")
    assert bills == []


@pytest.mark.asyncio
async def test_search_bills_fallback(bill_service, mock_client):
    async def side_effect(service_id_or_name, params, **kwargs):
        if params.get("AGE") == "22":
            return []
        if params.get("AGE") == "21":
            return [
                {
                    "BILL_ID": "2100001",
                    "BILL_NAME": "Fallback Bill",
                    "PROPOSE_DT": "20200101",
                    "LINK_URL": "http://test.com",
                }
            ]
        return []

    mock_client.get_data = AsyncMock(side_effect=side_effect)

    bills = await bill_service.search_bills("keyword")

    assert len(bills) == 1
    assert bills[0].BILL_NAME == "Fallback Bill"
    assert mock_client.get_data.call_count == 2


@pytest.mark.asyncio
async def test_get_recent_bills_sorting(bill_service, mock_client):
    mock_client.get_data = AsyncMock(
        return_value=[
            {"BILL_ID": "1", "BILL_NAME": "Old", "PROPOSE_DT": "20230101", "LINK_URL": "x"},
            {"BILL_ID": "2", "BILL_NAME": "New", "PROPOSE_DT": "20231231", "LINK_URL": "x"},
            {"BILL_ID": "3", "BILL_NAME": "Mid", "PROPOSE_DT": "20230601", "LINK_URL": "x"},
        ]
    )

    bills = await bill_service.get_recent_bills(limit=3)

    assert len(bills) == 3
    assert bills[0].BILL_NAME == "New"
    assert bills[1].BILL_NAME == "Mid"
    assert bills[2].BILL_NAME == "Old"


@pytest.mark.asyncio
async def test_get_bill_details(bill_service, mock_client):
    async def side_effect(service_id_or_name, params, **kwargs):
        if service_id_or_name == bill_service.BILL_SEARCH_ID:
            return [
                {
                    "BILL_ID": "PRC_X1Y2Z3A4B5C6D7E8",
                    "BILL_NO": "2200001",
                    "BILL_NAME": "Detail Bill",
                    "PROPOSE_DT": "20240101",
                    "LINK_URL": "http://test.com",
                }
            ]
        if service_id_or_name == bill_service.BILL_DETAIL_ID:
            assert "BILL_NO" in params
            assert params["BILL_NO"] == "2200001"
            return [{"MAIN_CNTS": "This is the summary.", "RSON_CONT": "This is the reason."}]
        return []

    mock_client.get_data = AsyncMock(side_effect=side_effect)

    detail = await bill_service.get_bill_details("PRC_X1Y2Z3A4B5C6D7E8")

    assert detail is not None
    assert detail.BILL_ID == "PRC_X1Y2Z3A4B5C6D7E8"
    assert detail.BILL_NO == "2200001"
    assert detail.BILL_NAME == "Detail Bill"
    assert detail.MAJOR_CONTENT == "This is the summary."
    assert detail.PROPOSE_REASON == "This is the reason."


@pytest.mark.asyncio
async def test_bill_model_captures_both_ids(bill_service, mock_client):
    """Test that Bill model captures both BILL_ID and BILL_NO separately."""
    mock_client.get_data = AsyncMock(
        return_value=[
            {
                "BILL_ID": "PRC_ALPHA123BETA456",
                "BILL_NO": "2123709",
                "BILL_NAME": "Test Bill with Both IDs",
                "PROPOSE_DT": "20240101",
                "LINK_URL": "http://test.com",
            }
        ]
    )

    bills = await bill_service.get_bill_info(age="22", limit=1)

    assert len(bills) == 1
    bill = bills[0]
    assert bill.BILL_ID == "PRC_ALPHA123BETA456"
    assert bill.BILL_NO == "2123709"


@pytest.mark.asyncio
async def test_bill_model_fallback_when_bill_id_missing(bill_service, mock_client):
    """Test that bill_id falls back to BILL_NO when BILL_ID is missing."""
    mock_client.get_data = AsyncMock(
        return_value=[
            {
                "BILL_NO": "2123709",
                "BILL_NAME": "Test Bill without BILL_ID",
                "PROPOSE_DT": "20240101",
                "LINK_URL": "http://test.com",
            }
        ]
    )

    bills = await bill_service.get_bill_info(age="22", limit=1)

    assert len(bills) == 1
    bill = bills[0]
    assert bill.BILL_ID == "2123709"
    assert bill.BILL_NO == "2123709"


@pytest.mark.asyncio
async def test_get_bill_details_uses_bill_no(bill_service, mock_client):
    """Test that get_bill_details uses BILL_NO parameter when calling detail API."""
    call_params = {}

    async def side_effect(service_id_or_name, params, **kwargs):
        if service_id_or_name == bill_service.BILL_SEARCH_ID:
            return [
                {
                    "BILL_ID": "PRC_TEST123",
                    "BILL_NO": "9999999",
                    "BILL_NAME": "Test Bill",
                    "PROPOSE_DT": "20240101",
                    "LINK_URL": "http://test.com",
                }
            ]
        if service_id_or_name == bill_service.BILL_DETAIL_ID:
            call_params.update(params)
            return [{"MAIN_CNTS": "Summary", "RSON_CONT": "Reason"}]
        return []

    mock_client.get_data = AsyncMock(side_effect=side_effect)

    await bill_service.get_bill_details("PRC_TEST123")

    assert "BILL_NO" in call_params
    assert call_params["BILL_NO"] == "9999999"
