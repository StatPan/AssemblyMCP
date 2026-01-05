from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import BillService, CommitteeService, MeetingService, MemberService
from assemblymcp.smart import SmartService


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_data = AsyncMock()
    return client


@pytest.fixture
def bill_service(mock_client):
    return BillService(mock_client)


@pytest.fixture
def committee_service(mock_client):
    return CommitteeService(mock_client)


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
async def test_search_bills_enhanced(bill_service, mock_client):
    # Mock response for bill search
    mock_client.get_data.return_value = {
        "O4K6HM0012064I15889": [
            {"head": [{"list_total_count": 1}, {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상"}}]},
            {
                "row": [
                    {
                        "BILL_ID": "PRC_123",
                        "BILL_NAME": "테스트 법안",
                        "PROPOSER": "김철수",
                        "PROPOSER_KIND": "의원",
                        "PROC_STATUS": "접수",
                        "CURR_COMMITTEE": "법사위",
                        "PROPOSE_DT": "20240101",
                    }
                ]
            },
        ]
    }

    bills = await bill_service.get_bill_info(age="22", bill_name="테스트")
    assert len(bills) == 1
    assert bills[0].BILL_ID == "PRC_123"
    assert bills[0].BILL_NAME == "테스트 법안"


@pytest.mark.asyncio
async def test_smart_service_analyze(smart_service, mock_client):
    # Mock for bill search
    mock_client.get_data.side_effect = [
        # search_bills
        {
            "O4K6HM0012064I15889": [
                {"head": []},
                {
                    "row": [
                        {
                            "BILL_ID": "PRC_1",
                            "BILL_NAME": "AI 법안",
                            "PROPOSER": "김철수",
                            "PROPOSER_KIND": "의원",
                            "PROC_STATUS": "접수",
                            "CURR_COMMITTEE": "과방위",
                        }
                    ]
                },
            ]
        },
        # get_bill_details (basic info Probe)
        {
            "O4K6HM0012064I15889": [
                {"head": []},
                {
                    "row": [
                        {
                            "BILL_ID": "PRC_1",
                            "BILL_NAME": "AI 법안",
                            "PROPOSER": "김철수",
                            "PROPOSER_KIND": "의원",
                            "PROC_STATUS": "접수",
                            "CURR_COMMITTEE": "과방위",
                        }
                    ]
                },
            ]
        },
        # get_bill_details (detail)
        {
            "OS46YD0012559515463": [
                {"head": []},
                {"row": [{"MAIN_CNTS": "AI 진흥 내용", "RSON_CONT": "필요성"}]},
            ]
        },
        # get_meeting_records
        {
            "OOWY4R001216HX11492": [
                {"head": []},
                {"row": [{"CONF_TITLE": "1차 회의"}]},
            ]
        },
        # get_member_info
        {
            "OWSSC6001134T516707": [
                {"head": []},
                {"row": [{"HG_NM": "김철수", "POLY_NM": "국민의힘"}]},
            ]
        },
    ]

    report = await smart_service.analyze_legislative_issue("AI")
    assert report["topic"] == "AI"
    assert len(report["recent_bills"]) > 0
    assert report["summary"]["latest_bill"]["BILL_ID"] == "PRC_1"
    assert report["summary"]["key_discussion_points"] == "AI 진흥 내용"
