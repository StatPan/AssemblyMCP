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


@pytest.mark.asyncio
async def test_get_bill_info_empty(bill_service, mock_client):
    mock_client.get_data = AsyncMock(return_value={})
    bills = await bill_service.get_bill_info(age="21")
    assert bills == []
