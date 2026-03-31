from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    mock.get_data = AsyncMock()
    return mock


@pytest.fixture
def smart_service(mock_client):
    bill_svc = BillService(mock_client)
    meeting_svc = MeetingService(mock_client)
    member_svc = MemberService(mock_client)
    return SmartService(bill_svc, meeting_svc, member_svc)


@pytest.mark.asyncio
async def test_get_legislative_reports(smart_service, mock_client):
    mock_client.get_data.side_effect = [
        # NABO Focus
        [{"SUBJECT": "보고서1", "REG_DATE": "2024-01-01", "LINK_URL": "http://nabo.go.kr/1"}],
        # News
        [{"V_TITLE": "뉴스1", "DATE_RELEASED": "2024-01-02", "URL_LINK": "http://news.go.kr/1"}],
    ]

    reports = await smart_service.get_legislative_reports("AI")

    assert len(reports) == 2
    assert reports[0].source == "국회예산정책처 (NABO)"
    assert reports[1].title == "뉴스1"


@pytest.mark.asyncio
async def test_get_committee_work_summary(smart_service, mock_client):
    mock_client.get_data.side_effect = [
        # Recent Bills
        [
            {
                "BILL_ID": "PRC_1",
                "BILL_NAME": "법사위 법안",
                "CURR_COMMITTEE": "법제사법위원회",
                "PROPOSER": "의원1",
                "PROPOSER_KIND": "의원",
                "PROC_STATUS": "접수",
                "LINK_URL": "x",
            }
        ],
        # Reports (NABO)
        [],
        # News
        [],
    ]

    summary = await smart_service.get_committee_work_summary("법사위")
    assert "법제사법위원회" in summary.committee_name
    assert len(summary.pending_bills_sample) == 1
    assert summary.pending_bills_sample[0].BILL_NAME == "법사위 법안"


@pytest.mark.asyncio
async def test_analyze_committee_performance(smart_service, mock_client):
    mock_client.get_data.side_effect = [
        [],  # 22nd bills (empty)
        [
            {
                "BILL_ID": "PRC_21_1",
                "BILL_NAME": "가결법안",
                "CURR_COMMITTEE": "법제사법위원회",
                "PROC_STATUS": "원안가결",
                "LINK_URL": "x",
            }
        ],  # 21st bills
        [{"BILL_ID": "PRC_21_1", "VOTE_TCNT": 100, "YES_TCNT": 90, "PROC_RESULT_CD": "가결"}],  # Voting summary
        [],  # Reports
        [],  # News
    ]

    report = await smart_service.get_committee_voting_stats("법사위")
    assert report.committee_name == "법제사법위원회"
    assert report.avg_yes_rate == 90.0
