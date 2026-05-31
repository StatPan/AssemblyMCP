import json
from unittest.mock import AsyncMock, patch

import pytest

from assemblymcp.models import Bill, BillDetail, BillVotingSummary, Committee, LegislativeReport
from assemblymcp.server import (
    bill_timeline,
    get_legislative_research_kit,
    issue_brief,
    legislative_impact_map,
    verify_legislative_claims,
    watch_action_plan,
)


def sample_bill(**overrides):
    data = {
        "BILL_ID": "PRC_SAMPLE",
        "BILL_NO": "2200001",
        "BILL_NAME": "인공지능 기본법안",
        "PROPOSER": "홍길동 의원 등 10인",
        "PROPOSER_KIND_NM": "의원",
        "PROC_STATUS": "위원회 심사",
        "CURR_COMMITTEE": "과학기술정보방송통신위원회",
        "PROPOSE_DT": "2024-06-01",
        "COMMITTEE_DT": "2024-06-10",
        "PROC_DT": "2024-07-01",
        "LINK_URL": "https://example.com/bill",
        "PRIMARY_PROPOSER": "홍길동",
    }
    data.update(overrides)
    return Bill(**data)


def sample_detail(**overrides):
    return BillDetail(
        **sample_bill(**overrides).model_dump(),
        MAJOR_CONTENT="인공지능 정책 기반을 마련합니다.",
        PROPOSE_REASON="산업 진흥 및 안전 확보",
    )


def sample_vote(**overrides):
    data = {
        "BILL_ID": "PRC_SAMPLE",
        "BILL_NAME": "인공지능 기본법안",
        "PROC_DT": "2024-07-01",
        "MEMBER_TCNT": 300,
        "VOTE_TCNT": 250,
        "YES_TCNT": 200,
        "NO_TCNT": 30,
        "BLANK_TCNT": 20,
        "PROC_RESULT_CD": "가결",
    }
    data.update(overrides)
    return BillVotingSummary(**data)


@pytest.mark.asyncio
async def test_get_legislative_research_kit_contract():
    result = await get_legislative_research_kit.fn()

    assert "verify_legislative_claims" in result["public_workflow_tools"]
    assert result["failure_markers"]["ambiguous"] == "[AMBIGUOUS]"


@pytest.mark.asyncio
async def test_verify_legislative_claims_success_for_bill_member_committee():
    with (
        patch("assemblymcp.server.bill_service") as mock_bill,
        patch("assemblymcp.server.member_service") as mock_member,
        patch("assemblymcp.server.committee_service") as mock_committee,
    ):
        mock_bill.get_bill_details = AsyncMock(return_value=sample_detail())
        mock_member.get_member_info = AsyncMock(return_value=[{"HG_NM": "홍길동", "POLY_NM": "테스트정당"}])
        mock_committee.get_committee_list = AsyncMock(
            return_value=[
                Committee(
                    HR_DEPT_CD="9700008",
                    COMMITTEE_NAME="과학기술정보방송통신위원회",
                    CMT_DIV_NM="상임위원회",
                )
            ]
        )
        claims = [
            {"type": "bill", "value": "PRC_SAMPLE", "expected": {"status": "위원회 심사"}},
            {"type": "member", "value": "홍길동"},
            {"type": "committee", "value": "과학기술정보방송통신위원회"},
        ]

        result = await verify_legislative_claims.fn(json.dumps(claims, ensure_ascii=False), age="22")

    assert result["ok"] is True
    assert result["verified_count"] == 3
    assert {item["entity_type"] for item in result["results"]} == {"bill", "member", "committee"}


@pytest.mark.asyncio
async def test_verify_legislative_claims_marks_ambiguous_bill_search():
    with patch("assemblymcp.server.bill_service") as mock_bill:
        mock_bill.get_bill_info = AsyncMock(
            return_value=[
                sample_bill(BILL_ID="PRC_1", BILL_NAME="인공지능 산업법안"),
                sample_bill(BILL_ID="PRC_2", BILL_NAME="인공지능 안전법안"),
            ]
        )

        result = await verify_legislative_claims.fn('{"type": "bill", "value": "인공지능"}')

    assert result["ok"] is False
    assert result["results"][0]["marker"] == "[AMBIGUOUS]"
    assert len(result["results"][0]["details"]["candidates"]) == 2


@pytest.mark.asyncio
async def test_verify_legislative_claims_marks_vote_mismatch():
    with patch("assemblymcp.server.bill_service") as mock_bill:
        mock_bill.get_bill_voting_summary = AsyncMock(return_value=sample_vote(YES_TCNT=200))

        result = await verify_legislative_claims.fn(
            '{"type": "vote", "bill_id": "PRC_SAMPLE", "expected": {"yes": 201}}'
        )

    assert result["ok"] is False
    assert result["results"][0]["marker"] == "[VERIFY_FAILED]"
    assert result["results"][0]["details"]["mismatches"][0]["field"] == "YES_TCNT"


@pytest.mark.asyncio
async def test_issue_brief_combines_bills_reports_meetings_and_votes():
    with (
        patch("assemblymcp.server.bill_service") as mock_bill,
        patch("assemblymcp.server.meeting_service") as mock_meeting,
        patch("assemblymcp.server.smart_service") as mock_smart,
    ):
        mock_bill.get_bill_info = AsyncMock(return_value=[sample_bill()])
        mock_bill.get_bill_voting_summary = AsyncMock(return_value=sample_vote())
        mock_meeting.search_meetings = AsyncMock(
            return_value=[{"CONF_DATE": "20240620", "CONF_TITLE": "전체회의", "COMM_NAME": "과방위"}]
        )
        mock_smart.get_legislative_reports = AsyncMock(
            return_value=[LegislativeReport(source="NABO", title="AI 보고서", date="2024-06-05")]
        )

        result = await issue_brief.fn(topic="인공지능", age="22", limit=5)

    assert result["summary"]["bill_count"] == 1
    assert result["summary"]["meeting_count"] == 1
    assert result["reports"][0]["title"] == "AI 보고서"
    assert result["voting_signal"][0]["YES_TCNT"] == 200
    assert result["follow_up"][0]["tool"] == "bill_timeline"


@pytest.mark.asyncio
async def test_bill_timeline_returns_normalized_event_schema():
    with (
        patch("assemblymcp.server.bill_service") as mock_bill,
        patch("assemblymcp.server.meeting_service") as mock_meeting,
    ):
        mock_bill.get_bill_details = AsyncMock(return_value=sample_detail())
        mock_bill.get_bill_voting_summary = AsyncMock(return_value=sample_vote())
        mock_meeting.get_meeting_records = AsyncMock(
            return_value=[{"CONF_DATE": "20240620", "CONF_TITLE": "전체회의", "COMM_NAME": "과방위"}]
        )

        result = await bill_timeline.fn(bill_id="PRC_SAMPLE", age="22")

    event_types = {item["event_type"] for item in result["events"]}
    assert {"introduced", "referred_to_committee", "committee_meeting", "plenary_vote", "final_disposition"}.issubset(
        event_types
    )
    assert all("source_tool" in item for item in result["events"])


@pytest.mark.asyncio
async def test_legislative_impact_map_for_topic_returns_nodes_edges_and_mermaid():
    with (
        patch("assemblymcp.server.bill_service") as mock_bill,
        patch("assemblymcp.server.meeting_service") as mock_meeting,
        patch("assemblymcp.server.smart_service") as mock_smart,
    ):
        mock_bill.get_bill_info = AsyncMock(return_value=[sample_bill()])
        mock_bill.get_bill_voting_summary = AsyncMock(return_value=sample_vote())
        mock_meeting.search_meetings = AsyncMock(return_value=[])
        mock_smart.get_legislative_reports = AsyncMock(
            return_value=[LegislativeReport(source="NABO", title="AI 보고서", date="2024-06-05")]
        )

        result = await legislative_impact_map.fn(target="인공지능", target_type="topic", age="22", limit=5)

    assert result["target_type"] == "topic"
    assert any(node["type"] == "bill" for node in result["nodes"])
    assert any(edge["relation"] == "matches_topic" for edge in result["edges"])
    assert result["mermaid"].startswith("graph TD")


@pytest.mark.asyncio
async def test_watch_action_plan_returns_five_steps_and_next_calls():
    with (
        patch("assemblymcp.server.bill_service") as mock_bill,
        patch("assemblymcp.server.meeting_service") as mock_meeting,
        patch("assemblymcp.server.smart_service") as mock_smart,
    ):
        mock_bill.get_bill_info = AsyncMock(return_value=[sample_bill()])
        mock_bill.get_bill_voting_summary = AsyncMock(return_value=None)
        mock_meeting.search_meetings = AsyncMock(return_value=[])
        mock_smart.get_legislative_reports = AsyncMock(return_value=[])

        result = await watch_action_plan.fn(topic="인공지능", age="22", limit=5)

    assert len(result["plan"]) == 5
    assert result["next_tool_calls"][0]["tool"] == "issue_brief"
    assert any(call["tool"] == "get_plenary_schedule" for call in result["next_tool_calls"])
