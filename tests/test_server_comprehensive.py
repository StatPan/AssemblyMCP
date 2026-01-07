from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assemblymcp.server import (
    analyze_legislative_issue,
    get_bill_voting_results,
    get_legislative_reports,
    get_member_info,
    get_representative_report,
)


@pytest.mark.asyncio
async def test_analyze_legislative_issue_integration():
    """analyze_legislative_issue 도구가 각 서비스를 잘 조합하는지 테스트"""
    with patch("assemblymcp.server.smart_service") as mock_smart:
        mock_smart.analyze_legislative_issue = AsyncMock(
            return_value={"topic": "인공지능", "summary": {"total_bills_found": 1}}
        )

        result = await analyze_legislative_issue.fn(topic="인공지능")

        assert result["topic"] == "인공지능"
        mock_smart.analyze_legislative_issue.assert_called_once_with("인공지능", limit=5)


@pytest.mark.asyncio
async def test_get_representative_report_integration():
    """의원 종합 리포트 생성 도구 테스트"""
    with patch("assemblymcp.server.smart_service") as mock_smart:
        mock_report = MagicMock()
        mock_report.model_dump.return_value = {"member_name": "홍길동", "stats": {}}
        mock_smart.get_representative_report = AsyncMock(return_value=mock_report)

        result = await get_representative_report.fn(member_name="홍길동")

        assert result["member_name"] == "홍길동"
        mock_smart.get_representative_report.assert_called_once_with("홍길동")


@pytest.mark.asyncio
async def test_get_member_info_flow():
    """의원 정보 검색 도구 흐름 테스트"""
    with patch("assemblymcp.server.member_service") as mock_member:
        mock_member.get_member_info = AsyncMock(return_value=[{"HG_NM": "홍길동"}])

        result = await get_member_info.fn(name="홍길동")

        assert isinstance(result, list)
        assert result[0]["HG_NM"] == "홍길동"


@pytest.mark.asyncio
async def test_get_legislative_reports_empty():
    """보고서 검색 결과가 없을 때 메시지 반환 테스트"""
    with patch("assemblymcp.server.smart_service") as mock_smart:
        mock_smart.get_legislative_reports = AsyncMock(return_value=[])

        result = await get_legislative_reports.fn(keyword="우주전쟁")

        assert isinstance(result, str)
        assert "보고서나 뉴스를 찾을 수 없습니다" in result


@pytest.mark.asyncio
async def test_get_bill_voting_results_not_found():
    """표결 결과가 없을 때 메시지 반환 테스트"""
    with patch("assemblymcp.server.smart_service") as mock_smart:
        mock_smart.get_bill_voting_results = AsyncMock(return_value={"message": "데이터 없음"})

        result = await get_bill_voting_results.fn(bill_id="NON_EXIST")

        assert result == {"message": "데이터 없음"}  # SmartService가 딕셔너리를 반환하는 경우
