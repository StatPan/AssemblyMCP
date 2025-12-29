from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from assemblymcp.services import BillService, MeetingService, MemberService

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
