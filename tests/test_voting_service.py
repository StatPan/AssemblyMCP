
from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_data = AsyncMock()
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
async def test_get_bill_voting_summary(bill_service, mock_client):
    mock_client.get_data.return_value = {
        "OND1KZ0009677M13515": [
            {"head": []},
            {"row": [
                {
                    "BILL_ID": "PRC_V1",
                    "BILL_NAME": "테스트 법안",
                    "YES_TCNT": "150",
                    "NO_TCNT": "50",
                    "BLANK_TCNT": "10",
                    "VOTE_TCNT": "210",
                    "PROC_RESULT_CD": "가결"
                }
            ]}
        ]
    }

    summary = await bill_service.get_bill_voting_summary("PRC_V1")

    assert summary is not None
    assert summary.YES_TCNT == 150
    assert summary.PROC_RESULT_CD == "가결"

@pytest.mark.asyncio
async def test_get_member_voting_history(bill_service, mock_client):
    mock_client.get_data.return_value = {
        "OPR1MQ000998LC12535": [
            {"head": []},
            {"row": [
                {
                    "BILL_ID": "PRC_V1",
                    "BILL_NAME": "테스트 법안",
                    "HG_NM": "홍길동",
                    "RESULT_VOTE_MOD": "찬성",
                    "POLY_NM": "가나다당"
                }
            ]}
        ]
    }

    records = await bill_service.get_member_voting_history(name="홍길동")

    assert len(records) == 1
    assert records[0].HG_NM == "홍길동"
    assert records[0].RESULT_VOTE_MOD == "찬성"

@pytest.mark.asyncio
async def test_get_representative_report(smart_service, mock_client):
    # Mock multiple calls inside get_representative_report
    # 1. get_member_info
    # 2. get_bill_info
    # 3. get_member_committee_careers
    # 4. get_member_voting_history

    mock_client.get_data.side_effect = [
        # get_member_info (OWSSC6001134T516707)
        {"OWSSC6001134T516707": [{"row": [{"HG_NM": "홍길동", "POLY_NM": "가나다당"}]}]},
        # get_bill_info (O4K6HM0012064I15889)
        {"O4K6HM0012064I15889": [{"row": [{"BILL_ID": "B1", "BILL_NAME": "법안1", "PROPOSER": "홍길동", "PROPOSER_KIND": "의원", "PROC_STATUS": "접수"}]}]},
        # get_member_committee_careers (ORNDP7000993P115502)
        {"ORNDP7000993P115502": [{"row": [{"HG_NM": "홍길동", "PROFILE_SJ": "법사위 위원"}]}]},
        # get_member_voting_history (OPR1MQ000998LC12535)
        {"OPR1MQ000998LC12535": [{"row": [{"BILL_ID": "V1", "BILL_NAME": "법안1", "RESULT_VOTE_MOD": "찬성", "HG_NM": "홍길동"}]}]}
    ]

    report = await smart_service.get_representative_report("홍길동")

    assert report.member_name == "홍길동"
    assert len(report.recent_bills) == 1
    assert len(report.committee_careers) == 1
    assert report.summary_stats["total_bills_22nd"] == 1

@pytest.mark.asyncio
async def test_get_bill_voting_results(smart_service, mock_client):
    mock_client.get_data.side_effect = [
        # get_bill_voting_summary
        {"OND1KZ0009677M13515": [{"row": [{"BILL_ID": "V1", "BILL_NAME": "법안1", "YES_TCNT": "100"}]}]},
        # get_member_voting_history (sample)
        {"OPR1MQ000998LC12535": [{"row": [
            {"BILL_ID": "V1", "BILL_NAME": "법안1", "RESULT_VOTE_MOD": "찬성", "POLY_NM": "A당", "HG_NM": "의원1"},
            {"BILL_ID": "V1", "BILL_NAME": "법안1", "RESULT_VOTE_MOD": "반대", "POLY_NM": "B당", "HG_NM": "의원2"}
        ]}]}
    ]

    results = await smart_service.get_bill_voting_results("V1")

    assert results["voting_summary"]["YES_TCNT"] == 100
    assert results["party_trend_sample"]["A당"]["찬성"] == 1
    assert results["party_trend_sample"]["B당"]["반대"] == 1
