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
    # Mock API response
    mock_response = {
        "O4K6HM0012064I15889": [
            {
                "head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}],
                "row": [
                    {
                        "BILL_ID": "2100001",
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
                ],
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    bills = await bill_service.get_bill_info(age="21", limit=1)

    assert len(bills) == 1
    assert isinstance(bills[0], Bill)
    assert bills[0].bill_id == "2100001"
    assert bills[0].bill_name == "Test Bill"
    assert bills[0].proposer == "Test Proposer"

    # Verify API call parameters
    mock_client.get_data.assert_called_once()
    call_args = mock_client.get_data.call_args
    assert call_args.kwargs["service_id"] == "O4K6HM0012064I15889"
    assert call_args.kwargs["params"]["AGE"] == "21"
    assert call_args.kwargs["params"]["pSize"] == 1

    mock_client.get_data = AsyncMock(return_value={})
    bills = await bill_service.get_bill_info(age="21")
    assert bills == []


@pytest.mark.asyncio
async def test_search_bills_fallback(bill_service, mock_client):
    # Mock first call (age 22) returning empty
    # Mock second call (age 21) returning results

    # We need to handle multiple calls to get_data with different params
    async def side_effect(service_id, params, **kwargs):
        if params.get("AGE") == "22":
            return {}
        if params.get("AGE") == "21":
            return {
                "O4K6HM0012064I15889": [
                    {
                        "row": [
                            {
                                "BILL_ID": "2100001",
                                "BILL_NAME": "Fallback Bill",
                                "PROPOSE_DT": "20200101",
                                "LINK_URL": "http://test.com",
                            }
                        ]
                    }
                ]
            }
        return {}

    mock_client.get_data = AsyncMock(side_effect=side_effect)

    bills = await bill_service.search_bills("keyword")

    assert len(bills) == 1
    assert bills[0].bill_name == "Fallback Bill"
    assert mock_client.get_data.call_count == 2


@pytest.mark.asyncio
async def test_get_recent_bills_sorting(bill_service, mock_client):
    # Mock unsorted response
    mock_response = {
        "O4K6HM0012064I15889": [
            {
                "row": [
                    {"BILL_ID": "1", "BILL_NAME": "Old", "PROPOSE_DT": "20230101", "LINK_URL": "x"},
                    {"BILL_ID": "2", "BILL_NAME": "New", "PROPOSE_DT": "20231231", "LINK_URL": "x"},
                    {"BILL_ID": "3", "BILL_NAME": "Mid", "PROPOSE_DT": "20230601", "LINK_URL": "x"},
                ]
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    bills = await bill_service.get_recent_bills(limit=3)

    assert len(bills) == 3
    assert bills[0].bill_name == "New"  # 2023-12-31
    assert bills[1].bill_name == "Mid"  # 2023-06-01
    assert bills[2].bill_name == "Old"  # 2023-01-01


@pytest.mark.asyncio
async def test_get_bill_details(bill_service, mock_client):
    # Mock basic info response
    basic_response = {
        "O4K6HM0012064I15889": [
            {
                "row": [
                    {
                        "BILL_ID": "2200001",
                        "BILL_NAME": "Detail Bill",
                        "PROPOSE_DT": "20240101",
                        "LINK_URL": "http://test.com",
                    }
                ]
            }
        ]
    }

    # Mock detail info response
    detail_response = {
        "OS46YD0012559515463": [
            {"row": [{"MAIN_CNTS": "This is the summary.", "RSON_CONT": "This is the reason."}]}
        ]
    }

    async def side_effect(service_id, params, **kwargs):
        if service_id == bill_service.BILL_SEARCH_ID:
            return basic_response
        if service_id == bill_service.BILL_DETAIL_ID:
            return detail_response
        return {}

    mock_client.get_data = AsyncMock(side_effect=side_effect)

    detail = await bill_service.get_bill_details("2200001")

    assert detail is not None
    assert detail.bill_name == "Detail Bill"
    assert detail.summary == "This is the summary."
    assert detail.reason == "This is the reason."
