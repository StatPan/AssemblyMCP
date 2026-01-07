from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from assemblymcp.models import (
    CommitteeVotingStats,
    CommitteeWorkSummary,
    LegislativeReport,
    MemberActivityReport,
    TopicVotingStats,
)

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
        clean_name = name.strip().replace(" ", "")
        return COMMITTEE_ALIASES.get(clean_name, clean_name)

    async def get_legislative_reports(self, keyword: str, limit: int = 5) -> list[LegislativeReport]:
        import json

        from assemblymcp.services import _collect_rows

        reports = []

        async def fetch_nabo():
            try:
                raw_data = await self.bill_service.client.get_data(
                    "OB5IBW001180FQ10640", params={"SUBJECT": keyword, "pSize": limit}
                )
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)

                rows = _collect_rows(raw_data)
                return (
                    [
                        LegislativeReport(
                            source="국회예산정책처 (NABO)",
                            title=item.get("SUBJECT", ""),
                            date=item.get("REG_DATE", "")[:10] if item.get("REG_DATE") else None,
                            link=item.get("LINK_URL"),
                            report_type="분석보고서",
                        )
                        for item in rows
                    ]
                    if rows
                    else []
                )
            except Exception as e:
                logger.warning(f"NABO 보고서 조회 중 오류 발생 (키워드: '{keyword}'): {e}")
                return []

        async def fetch_news():
            try:
                raw_data = await self.bill_service.client.get_data(
                    "O5MSQF0009823A15643", params={"V_TITLE": keyword, "pSize": limit}
                )
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)

                rows = _collect_rows(raw_data)
                return (
                    [
                        LegislativeReport(
                            source="국회뉴스ON",
                            title=item.get("V_TITLE", ""),
                            date=item.get("DATE_RELEASED", "")[:10] if item.get("DATE_RELEASED") else None,
                            link=item.get("URL_LINK"),
                            report_type="뉴스/브리핑",
                        )
                        for item in rows
                    ]
                    if rows
                    else []
                )
            except Exception as e:
                logger.warning(f"국회뉴스ON 조회 중 오류 발생 (키워드: '{keyword}'): {e}")
                return []

        results = await asyncio.gather(fetch_nabo(), fetch_news())
        for res_list in results:
            reports.extend(res_list)

        return reports[: limit * 2]

    async def get_committee_work_summary(self, committee_name: str) -> CommitteeWorkSummary:
        normalized_target = self._normalize_committee_name(committee_name)
        bills_task = self.bill_service.get_recent_bills(limit=30)
        reports_task = self.get_legislative_reports(normalized_target, limit=3)

        bills, reports = await asyncio.gather(bills_task, reports_task)

        relevant_bills = [
            b for b in bills if normalized_target in self._normalize_committee_name(b.CURR_COMMITTEE or "")
        ]

        return CommitteeWorkSummary(
            committee_name=normalized_target, pending_bills_sample=relevant_bills[:5], related_reports=reports
        )

    async def get_committee_voting_stats(self, committee_name: str) -> CommitteeVotingStats:
        normalized_name = self._normalize_committee_name(committee_name)
        chair_name = normalized_name + "장"

        relevant_bills = []
        target_age = "22"
        for age in ["22", "21"]:
            target_age = age
            bills = await self.bill_service.get_bill_info(age=age, limit=500)
            relevant_bills = [
                b
                for b in bills
                if (normalized_name in (b.CURR_COMMITTEE or "") or chair_name in (b.CURR_COMMITTEE or ""))
                and ("가결" in (b.PROC_STATUS or ""))
                and ("폐기" not in (b.PROC_STATUS or ""))
            ]
            if relevant_bills:
                break

        passed_analysis = []
        total_yes_rate = 0.0
        valid_vote_count = 0

        for bill in relevant_bills[:10]:
            summary = await self.bill_service.get_bill_voting_summary(bill.BILL_ID, age=target_age)
            if summary and summary.VOTE_TCNT and summary.VOTE_TCNT > 0:
                yes_rate = (summary.YES_TCNT / summary.VOTE_TCNT) * 100
                total_yes_rate += yes_rate
                valid_vote_count += 1
                passed_analysis.append(
                    {
                        "BILL_NAME": bill.BILL_NAME,
                        "YES_RATE": round(yes_rate, 2),
                        "VOTE_DATE": summary.PROC_DT,
                        "TOTAL_VOTES": summary.VOTE_TCNT,
                    }
                )

        avg_consensus = total_yes_rate / valid_vote_count if valid_vote_count > 0 else 0.0

        return CommitteeVotingStats(
            committee_name=normalized_name,
            assembly_age=target_age,
            avg_yes_rate=round(avg_consensus, 2),
            total_bills_analyzed=valid_vote_count,
            bills_detail=passed_analysis,
        )

    async def get_topic_voting_stats(self, keyword: str, limit: int = 10) -> TopicVotingStats:
        target_age = "22"
        passed_bills = []
        for age in ["22", "21"]:
            target_age = age
            bills = await self.bill_service.get_bill_info(age=age, bill_name=keyword, limit=100)
            passed_bills = [
                b for b in bills if ("가결" in (b.PROC_STATUS or "")) and ("폐기" not in (b.PROC_STATUS or ""))
            ]
            if passed_bills:
                break

        voting_results = []
        for b in passed_bills[:limit]:
            summary = await self.bill_service.get_bill_voting_summary(b.BILL_ID, age=target_age)
            if summary and summary.VOTE_TCNT and summary.VOTE_TCNT > 0:
                yes_rate = (summary.YES_TCNT / summary.VOTE_TCNT) * 100
                voting_results.append(
                    {
                        "BILL_NAME": b.BILL_NAME,
                        "YES_RATE": round(yes_rate, 2),
                        "VOTE_DATE": summary.PROC_DT,
                        "TOTAL_VOTES": summary.VOTE_TCNT,
                    }
                )

        avg_score = sum(b["YES_RATE"] for b in voting_results) / len(voting_results) if voting_results else 0.0

        return TopicVotingStats(
            keyword=keyword,
            assembly_age=target_age,
            avg_yes_rate=round(avg_score, 2),
            bill_count=len(voting_results),
            individual_results=voting_results,
        )

    async def get_bill_history(self, bill_id: str) -> list[dict[str, Any]]:
        details = await self.bill_service.get_bill_details(bill_id)
        meetings = await self.meeting_service.get_meeting_records(bill_id)
        history = []
        if not details:
            return []

        if details.PROPOSE_DT:
            history.append({"date": details.PROPOSE_DT, "event": "의안 발의", "note": f"제안자: {details.PROPOSER}"})
        if details.COMMITTEE_DT:
            history.append(
                {
                    "date": details.COMMITTEE_DT,
                    "event": "위원회 회부",
                    "note": f"소관위: {details.CURR_COMMITTEE}",
                }
            )
        if details.PROC_DT:
            history.append({"date": details.PROC_DT, "event": "최종 처리", "note": f"결과: {details.PROC_STATUS}"})

        for m in meetings:
            m_date = m.get("CONF_DATE")
            if m_date and len(m_date) == 8:
                m_date = f"{m_date[:4]}-{m_date[4:6]}-{m_date[6:]}"
            history.append(
                {
                    "date": m_date or "날짜 미상",
                    "event": "위원회 회의",
                    "note": f"{m.get('COMM_NAME', '')} {m.get('CONF_TITLE', '')}",
                }
            )

        history.sort(key=lambda x: x["date"] if x["date"] else "")
        return history

    async def analyze_legislative_issue(self, topic: str, limit: int = 5) -> dict[str, Any]:
        bills = await self.bill_service.search_bills(keyword=topic, limit=limit)
        if not bills:
            return {"topic": topic, "message": "데이터 없음"}

        main_bill = bills[0]
        details = await self.bill_service.get_bill_details(main_bill.BILL_ID)
        meetings = await self.meeting_service.get_meeting_records(main_bill.BILL_ID)

        proposers = []
        seen = set()
        for b in bills[:3]:
            if b.PRIMARY_PROPOSER and b.PRIMARY_PROPOSER not in seen:
                info = await self.member_service.get_member_info(b.PRIMARY_PROPOSER)
                if info:
                    proposers.append(info[0])
                    seen.add(b.PRIMARY_PROPOSER)

        return {
            "topic": topic,
            "summary": {
                "total_bills_found": len(bills),
                "latest_bill": main_bill.model_dump(exclude_none=True),
                "key_discussion_points": details.MAJOR_CONTENT if details else None,
            },
            "recent_bills": [b.model_dump(exclude_none=True) for b in bills],
            "relevant_meetings": meetings[:3] if meetings else [],
            "key_politicians": proposers,
        }

    async def get_representative_report(self, member_name: str) -> MemberActivityReport:
        info_task = self.member_service.get_member_info(member_name)
        bills_task = self.bill_service.get_bill_info(age="22", proposer=member_name, limit=5)
        careers_task = self.member_service.get_member_committee_careers(member_name)
        votes_task = self.bill_service.get_member_voting_history(name=member_name, limit=10)

        infos, bills, careers, votes = await asyncio.gather(info_task, bills_task, careers_task, votes_task)
        basic_info = infos[0] if infos else {"HG_NM": member_name}

        committee_durations = {}
        for c in careers:
            if not c.FRTO_DATE or "~" not in c.FRTO_DATE:
                continue

            dates = c.FRTO_DATE.split("~")
            try:
                from datetime import datetime

                start_dt = datetime.strptime(dates[0].strip(), "%Y.%m.%d")
                end_dt = (
                    datetime.strptime(dates[1].strip(), "%Y.%m.%d")
                    if len(dates) > 1 and dates[1].strip()
                    else datetime.now()
                )
                months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
                committee_durations[c.PROFILE_SJ] = committee_durations.get(c.PROFILE_SJ, 0) + max(1, months)
            except Exception:
                continue

        sorted_expert = sorted(committee_durations.items(), key=lambda x: x[1], reverse=True)
        summary_stats = {
            "total_bills_22nd": len(bills),
            "expertise": [f"{name}({m}개월)" for name, m in sorted_expert[:3]],
            "votes_tracked": len(votes),
        }

        return MemberActivityReport(
            member_name=member_name,
            basic_info=basic_info,
            recent_bills=bills,
            committee_careers=careers,
            recent_votes=votes,
            summary_stats=summary_stats,
        )

    async def get_bill_voting_results(self, bill_id: str) -> dict[str, Any]:
        summary = await self.bill_service.get_bill_voting_summary(bill_id)
        if not summary:
            return {"bill_id": bill_id, "message": "데이터 없음"}
        records = await self.bill_service.get_member_voting_history(bill_id=bill_id, limit=100)
        party_stats = {}
        for r in records:
            p = r.POLY_NM or "무소속"
            if p not in party_stats:
                party_stats[p] = {"찬성": 0, "반대": 0, "기권": 0}

            if "찬성" in r.RESULT_VOTE_MOD:
                party_stats[p]["찬성"] += 1
            elif "반대" in r.RESULT_VOTE_MOD:
                party_stats[p]["반대"] += 1
            elif "기권" in r.RESULT_VOTE_MOD:
                party_stats[p]["기권"] += 1
        return {"voting_summary": summary.model_dump(exclude_none=True), "party_trend_sample": party_stats}

    async def analyze_voting_trends(self, topic: str) -> dict[str, Any]:
        bills = await self.bill_service.search_bills(keyword=topic, limit=10)
        results = []
        for b in bills:
            if b.PROC_STATUS in ["의결", "본회의 심의"]:
                summary = await self.bill_service.get_bill_voting_summary(b.BILL_ID)
                if summary:
                    results.append(summary.model_dump(exclude_none=True))
        return {"topic": topic, "analyzed_count": len(results), "voting_summaries": results}
