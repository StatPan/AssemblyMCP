from __future__ import annotations
import asyncio
import logging
from typing import Any, TYPE_CHECKING
from assemblymcp.models import Bill, LegislativeReport, CommitteeWorkSummary

if TYPE_CHECKING:
    from assemblymcp.services import BillService, MeetingService, MemberService

logger = logging.getLogger(__name__)

COMMITTEE_ALIASES = {
    "법사위": "법제사법위원회",
    "정무위": "정무위원회",
    "기재위": "기획재정위원회",
    "교육위": "교육위원회",
    "과방위": "과학기술정보방송통신위원회",
    "외통위": "외교통일위원회",
    "국방위": "국방위원회",
    "행안위": "행정안전위원회",
    "문체위": "문화체육관광위원회",
    "농해수위": "농림축산식품해양수산위원회",
    "산업위": "산업통상자원중소벤처기업위원회",
    "산자위": "산업통상자원중소벤처기업위원회",
    "보복위": "보건복지위원회",
    "환노위": "환경노동위원회",
    "국토위": "국토교통위원회",
    "정보위": "정보위원회",
    "여가위": "여성가족위원회",
    "운영위": "국회운영위원회",
    "예결위": "예산결산특별위원회",
}

class SmartService:
    def __init__(
        self,
        bill_service: BillService,
        meeting_service: MeetingService,
        member_service: MemberService,
    ):
        self.bill_service = bill_service
        self.meeting_service = meeting_service
        self.member_service = member_service

    def _normalize_committee_name(self, name: str) -> str:
        """
        위원회명을 정규화합니다 (약어 변환 및 공백 제거).
        """
        clean_name = name.strip().replace(" ", "")
        # 약어 매핑 확인
        return COMMITTEE_ALIASES.get(clean_name, clean_name)

    async def get_legislative_reports(self, keyword: str, limit: int = 5) -> list[LegislativeReport]:
        """
        국회예산정책처(NABO) 및 국회 뉴스에서 관련 보고서와 소식을 검색합니다.
        """
        reports = []
        
        async def fetch_nabo():
            try:
                data = await self.bill_service.client.get(
                    "OB5IBW001180FQ10640", 
                    params={"SUBJECT": keyword, "pSize": limit}
                )
                return [
                    LegislativeReport(
                        source="국회예산정책처 (NABO)",
                        title=item.get("SUBJECT", ""),
                        date=item.get("REG_DATE"),
                        link=item.get("LINK_URL"),
                        report_type="분석보고서"
                    ) for item in data
                ] if data else []
            except Exception as e:
                logger.warning(f"NABO report fetch failed for '{keyword}': {e}")
                return []

        async def fetch_news():
            try:
                data = await self.bill_service.client.get(
                    "O5MSQF0009823A15643",
                    params={"TITLE": keyword, "pSize": limit}
                )
                return [
                    LegislativeReport(
                        source="국회뉴스ON",
                        title=item.get("TITLE", ""),
                        date=item.get("REG_DATE"),
                        link=item.get("LINK_URL"),
                        report_type="뉴스/브리핑"
                    ) for item in data
                ] if data else []
            except Exception as e:
                logger.warning(f"National Assembly News fetch failed for '{keyword}': {e}")
                return []

        # 병렬 호출로 성능 최적화
        results = await asyncio.gather(fetch_nabo(), fetch_news())
        for res_list in results:
            reports.extend(res_list)

        return reports[:limit * 2]

    async def get_committee_work_summary(self, committee_name: str) -> CommitteeWorkSummary:
        """
        위원회명을 바탕으로 소속 의원 명단과 현재 계류 중인 주요 법안들을 매핑하여 반환합니다.
        """
        normalized_target = self._normalize_committee_name(committee_name)
        
        # 1. 의안 검색과 보고서 검색을 병렬로 수행
        # 보고서 검색은 정규화된 이름(전체 이름)으로 수행하여 정확도 향상
        bills_task = self.bill_service.get_recent_bills(limit=30)
        reports_task = self.get_legislative_reports(normalized_target, limit=3)
        
        bills, reports = await asyncio.gather(bills_task, reports_task)

        # 2. 정규화된 이름으로 필터링
        relevant_bills = []
        for b in bills:
            curr_comm = (b.CURR_COMMITTEE or "")
            if normalized_target in self._normalize_committee_name(curr_comm):
                relevant_bills.append(b)

        return CommitteeWorkSummary(
            committee_name=normalized_target,  # 정규화된 전체 이름 반환
            pending_bills_sample=relevant_bills[:5],
            related_reports=reports,
            instruction=(
                f"상세 의원 명단이 필요하면 'get_committee_info(committee_name=\"{normalized_target}\")'를, "
                f"위원회 일정이 궁금하면 'search_meetings(committee_name=\"{normalized_target}\")'를 호출하세요."
            )
        )

    async def get_bill_history(self, bill_id: str) -> list[dict[str, Any]]:
        """
        의안의 발의부터 현재까지의 모든 주요 이력(회의 포함)을 날짜순으로 통합하여 반환합니다.
        LLM이 이 데이터를 바탕으로 타임라인을 그리거나 요약하는 데 사용합니다.
        """
        details = await self.bill_service.get_bill_details(bill_id)
        meetings = await self.meeting_service.get_meeting_records(bill_id)
        
        history = []
        
        if not details:
            return []

        # 1. 기본 이력 추출
        if details.PROPOSE_DT:
            history.append({"date": details.PROPOSE_DT, "event": "의안 발의", "note": f"제안자: {details.PROPOSER}"})
        
        if details.COMMITTEE_DT:
            history.append({"date": details.COMMITTEE_DT, "event": "위원회 회회부", "note": f"소관위: {details.CURR_COMMITTEE}"})
            
        if details.PROC_DT:
            history.append({"date": details.PROC_DT, "event": "최종 처리", "note": f"결과: {details.PROC_STATUS}"})

        # 2. 회의 이력 통합
        for m in meetings:
            m_date = m.get("CONF_DATE")
            # YYYYMMDD -> YYYY-MM-DD 변환
            if m_date and len(m_date) == 8:
                m_date = f"{m_date[:4]}-{m_date[4:6]}-{m_date[6:]}"
            
            history.append({
                "date": m_date or "날짜 미상",
                "event": "위원회 회의",
                "note": f"{m.get('COMM_NAME', '')} {m.get('CONF_TITLE', '')}"
            })

        # 3. 날짜순 정렬
        history.sort(key=lambda x: x["date"] if x["date"] else "")
        return history

    async def analyze_legislative_issue(self, topic: str, limit: int = 5) -> dict[str, Any]:
        """
        특정 주제(이슈)에 대한 종합적인 입법 현황 분석 리포트를 생성합니다.
        """
        bills = await self.bill_service.search_bills(keyword=topic, limit=limit)
        
        if not bills:
            return {"topic": topic, "message": "해당 주제와 관련된 최근 법안을 찾을 수 없습니다."}

        main_bill = bills[0]
        details = await self.bill_service.get_bill_details(main_bill.BILL_ID)
        meetings = await self.meeting_service.get_meeting_records(main_bill.BILL_ID)
        
        proposers = []
        seen_proposers = set()
        for b in bills[:3]:
            if b.PRIMARY_PROPOSER and b.PRIMARY_PROPOSER not in seen_proposers:
                member_info = await self.member_service.get_member_info(b.PRIMARY_PROPOSER)
                if member_info:
                    proposers.append(member_info[0])
                    seen_proposers.add(b.PRIMARY_PROPOSER)

        return {
            "topic": topic,
            "summary": {
                "total_bills_found": len(bills),
                "latest_bill": main_bill.model_dump(exclude_none=True),
                "key_discussion_points": details.MAJOR_CONTENT if details else None,
            },
            "recent_bills": [b.model_dump(exclude_none=True) for b in bills],
            "relevant_meetings": meetings[:3] if meetings else [],
            "key_politicians": proposers
        }
