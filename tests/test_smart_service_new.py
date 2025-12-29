
import pytest
from unittest.mock import AsyncMock, MagicMock
from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_data = AsyncMock()
    # Add client.get as well since SmartService uses it
    client.get = AsyncMock()
    return client

@pytest.fixture
def bill_service(mock_client):
    service = BillService(mock_client)
    service.client = mock_client
    return service

@pytest.fixture
def meeting_service(mock_client):
    return MeetingService(mock_client)

@pytest.fixture
def member_service(mock_client):
    return MemberService(mock_client)

@pytest.fixture
def smart_service(bill_service, meeting_service, member_service):
    return SmartService(bill_service, meeting_service, member_service)

@pytest.mark.asyncio
async def test_get_legislative_reports(smart_service, mock_client):
    # Mock for NABO Focus (OB5IBW001180FQ10640)
    # Mock for News (O5MSQF0009823A15643)
    mock_client.get.side_effect = [
        # NABO Focus
        [{"SUBJECT": "보고서1", "REG_DATE": "2024-01-01", "LINK_URL": "http://nabo.go.kr/1"}],
        # News
        [{"TITLE": "뉴스1", "REG_DATE": "2024-01-02", "LINK_URL": "http://news.go.kr/1"}]
    ]
    
    reports = await smart_service.get_legislative_reports("AI")
    
    assert len(reports) == 2
    assert reports[0].title == "보고서1"
    assert reports[0].source == "국회예산정책처 (NABO)"
    assert reports[1].title == "뉴스1"
    assert mock_client.get.call_count == 2

@pytest.mark.asyncio
async def test_get_committee_work_summary(smart_service, mock_client):
    # Mock for get_recent_bills (called via bill_service)
    mock_client.get_data.return_value = {
        "O4K6HM0012064I15889": [
            {"head": []},
            {"row": [
                {
                    "BILL_ID": "PRC_1", 
                    "BILL_NAME": "법사위 법안", 
                    "CURR_COMMITTEE": "법제사법위원회",
                    "PROPOSER": "의원1",
                    "PROPOSER_KIND": "의원",
                    "PROC_STATUS": "접수"
                }
            ]}
        ]
    }
    
    # Mock for get_legislative_reports (called via smart_service)
    mock_client.get.return_value = []
    
    summary = await smart_service.get_committee_work_summary("법사위")
    
    # Logic correctly normalized "법사위" to "법제사법위원회"
    assert summary.committee_name == "법제사법위원회"
    assert len(summary.pending_bills_sample) == 1
    assert summary.pending_bills_sample[0].BILL_NAME == "법사위 법안"
