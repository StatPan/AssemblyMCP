from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from assemblymcp.models import (
    CommitteeWorkSummary,
    LegislativeReport,
    MemberActivityReport,
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
        from assemblymcp.services import _collect_rows
        import json
        
        reports = []

        async def fetch_nabo():
            try:
                # NABO: REG_DATE, SUBJECT, LINK_URL
                raw_data = await self.bill_service.client.get_data(
                    "OB5IBW001180FQ10640",
                    params={"SUBJECT": keyword, "pSize": limit}
                )
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)
                
                rows = _collect_rows(raw_data)
                return [
                    LegislativeReport(
                        source="국회예산정책처 (NABO)",
                        title=item.get("SUBJECT", ""),
                        date=item.get("REG_DATE", "")[:10] if item.get("REG_DATE") else None,
                        link=item.get("LINK_URL"),
                        report_type="분석보고서"
                    ) for item in rows
                ] if rows else []
            except Exception as e:
                logger.warning(f"NABO report fetch failed for '{keyword}': {e}")
                return []

        async def fetch_news():
            try:
                # News: V_TITLE, URL_LINK, DATE_RELEASED
                # Note: API spec says V_TITLE is the request param for searching by title
                raw_data = await self.bill_service.client.get_data(
                    "O5MSQF0009823A15643",
                    params={"V_TITLE": keyword, "pSize": limit}
                )
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)
                
                rows = _collect_rows(raw_data)
                return [
                    LegislativeReport(
                        source="국회뉴스ON",
                        title=item.get("V_TITLE", ""),
                        date=item.get("DATE_RELEASED", "")[:10] if item.get("DATE_RELEASED") else None,
                        link=item.get("URL_LINK"),
                        report_type="뉴스/브리핑"
                    ) for item in rows
                ] if rows else []
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

    async def analyze_committee_performance(self, committee_name: str) -> CommitteePerformanceReport:
        """
        위원회 성과 및 협치 분석 리포트를 생성합니다.
        가결된 법안의 찬성률을 통해 위원회의 협치 정도를 파악합니다.
        """
        from assemblymcp.models import CommitteePerformanceReport
        
        normalized_name = self._normalize_committee_name(committee_name)
        # 위원장 명의 법안도 매칭되도록 함 (예: '법제사법위원장')
        chair_name = normalized_name + "장"
        
        # 1. 위원회에서 가결된 최근 법안들 조회 (22대 우선, 없으면 21대)
        # 검색 범위와 유연성 극대화
        relevant_bills = []
        for age in ["22", "21"]:
            # 가결된 법안을 찾기 위해 검색 범위를 넓게 잡음 (21대의 경우 폐기된 법안이 많음)
            bills = await self.bill_service.get_bill_info(
                age=age, 
                limit=500 # 데이터 확보를 위해 대폭 확대
            )
            
            # '폐기'를 제외하고 '가결'이 포함된 것만 필터링
            relevant_bills = [
                b for b in bills 
                if (normalized_name in (b.CURR_COMMITTEE or "") or chair_name in (b.CURR_COMMITTEE or ""))
                and ("가결" in (b.PROC_STATUS or ""))
                and ("폐기" not in (b.PROC_STATUS or ""))
            ]
            if relevant_bills:
                break
        
        # 2. 표결 결과 집계 (최대 10건 분석하여 정확도 향상)
        passed_analysis = []
        total_yes_rate = 0.0
        valid_vote_count = 0
        
        for bill in relevant_bills[:10]: 
            summary = await self.bill_service.get_bill_voting_summary(bill.BILL_ID, age=bill.BILL_ID[4:6] if "PRC_" in bill.BILL_ID else "22")
            # 만약 위 로직으로 age를 못 구하면 21대 우선 시도 (가결 데이터가 많으므로)
            if not summary:
                summary = await self.bill_service.get_bill_voting_summary(bill.BILL_ID, age="21")
                
            if summary and summary.VOTE_TCNT and summary.VOTE_TCNT > 0:
                yes_rate = (summary.YES_TCNT / summary.VOTE_TCNT) * 100
                total_yes_rate += yes_rate
                valid_vote_count += 1
                
                passed_analysis.append({
                    "bill_name": bill.BILL_NAME,
                    "yes_rate": round(yes_rate, 2),
                    "result": summary.PROC_RESULT_CD,
                    "date": summary.PROC_DT
                })

        # 3. 보고서 연동
        reports = await self.get_legislative_reports(normalized_name, limit=3)
        if not reports:
            reports = await self.get_legislative_reports(committee_name, limit=3)

        # 4. 통계 및 요약 생성
        avg_consensus = total_yes_rate / valid_vote_count if valid_vote_count > 0 else 0
        
        if valid_vote_count > 0:
            summary_text = f"{normalized_name}은(는) 분석된 {valid_vote_count}건의 가결 법안에서 "
            summary_text += f"평균 {round(avg_consensus, 1)}%의 찬성률을 기록했습니다. "
            if avg_consensus > 90:
                summary_text += "정당 간 이견 없이 합의가 잘 이루어지는 '협치형' 위원회로 분석됩니다."
            elif avg_consensus > 75:
                summary_text += "비교적 원만한 입법 협의가 진행되는 위원회입니다."
            else:
                summary_text += "법안 처리 과정에서 정당 간의 뚜렷한 입장 차이가 나타나기도 합니다."
        else:
            summary_text = f"{normalized_name}의 최근 가결 법안에 대한 상세 표결 데이터를 조회할 수 없습니다. "
            summary_text += "(데이터 업데이트 지연 또는 검색 범위 외 기록)"

        return CommitteePerformanceReport(
            committee_name=normalized_name,
            stats={
                "analyzed_bills_count": valid_vote_count,
                "average_yes_rate": round(avg_consensus, 2),
            },
            passed_bills_analysis=passed_analysis,
            nabo_fiscal_data=reports,
            consensus_score=round(avg_consensus, 2),
            summary=summary_text
        )

    async def get_topic_political_consensus(self, topic: str, limit: int = 10) -> TopicConsensusReport:
        """
        특정 주제(이슈)와 관련된 가결 법안들의 찬성률을 분석하여 정당 간 합의 수준을 리포트합니다.
        """
        from assemblymcp.models import TopicConsensusReport
        
        # 1. 관련 법안 검색 (최근 2대 국회 범위)
        bills = await self.bill_service.search_bills(keyword=topic, limit=50)
        
        # 가결된 법안만 추출
        passed_bills = [
            b for b in bills 
            if ("가결" in (b.PROC_STATUS or "")) and ("폐기" not in (b.PROC_STATUS or ""))
        ]
        
        if not passed_bills:
            return TopicConsensusReport(
                topic=topic,
                overall_consensus_score=0.0,
                analyzed_bills_count=0,
                bills_detail=[],
                consensus_trend=f"'{topic}' 관련 최근 가결 법안이 없어 분석을 수행할 수 없습니다."
            )

        # 2. 각 법안의 표결 데이터 수집 (병렬 처리)
        results = []
        total_yes_rate = 0.0
        
        async def fetch_voting_data(bill):
            # Bill ID에서 대수 추출 시도 (PRC_21... -> 21)
            age = "21" if "PRC_21" in bill.BILL_ID else "22"
            summary = await self.bill_service.get_bill_voting_summary(bill.BILL_ID, age=age)
            if summary and summary.VOTE_TCNT and summary.VOTE_TCNT > 0:
                yes_rate = (summary.YES_TCNT / summary.VOTE_TCNT) * 100
                return {
                    "bill_name": bill.BILL_NAME,
                    "yes_rate": round(yes_rate, 2),
                    "date": summary.PROC_DT,
                    "result": summary.PROC_RESULT_CD
                }
            return None

        # 병렬 호출로 시간 단축
        voting_tasks = [fetch_voting_data(b) for b in passed_bills[:limit]]
        voting_results = await asyncio.gather(*voting_tasks)
        
        final_bills_detail = [r for r in voting_results if r is not None]
        
        if not final_bills_detail:
            return TopicConsensusReport(
                topic=topic,
                overall_consensus_score=0.0,
                analyzed_bills_count=0,
                bills_detail=[],
                consensus_trend="관련 법안의 상세 표결 기록을 찾을 수 없습니다."
            )

        # 3. 종합 지수 계산
        avg_score = sum(b["yes_rate"] for b in final_bills_detail) / len(final_bills_detail)
        
        # 4. 경향 분석 메시지 생성
        if avg_score > 90:
            trend = f"'{topic}' 관련 법안들은 초당적인 합의가 매우 잘 이루어지는 분야입니다."
        elif avg_score > 70:
            trend = f"'{topic}' 이슈는 대체로 원만하게 합의되나 일부 쟁점이 존재할 수 있습니다."
        else:
            trend = f"'{topic}' 이슈는 정당 간 입장 차이가 뚜렷하게 나타나는 쟁점 분야입니다."

        return TopicConsensusReport(
            topic=topic,
            overall_consensus_score=round(avg_score, 2),
            analyzed_bills_count=len(final_bills_detail),
            bills_detail=final_bills_detail,
            consensus_trend=trend
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

    async def get_representative_report(self, member_name: str) -> MemberActivityReport:
        """
        특정 국회의원의 종합 의정활동 리포트를 생성합니다.
        인적사항, 최근 대표 발의 법안, 위원회 경력(기간 분석), 최근 본회의 투표 이력을 통합합니다.
        """
        # 1. 여러 데이터를 병렬로 조회
        info_task = self.member_service.get_member_info(member_name)
        bills_task = self.bill_service.get_bill_info(age="22", proposer=member_name, limit=5)
        careers_task = self.member_service.get_member_committee_careers(member_name)
        votes_task = self.bill_service.get_member_voting_history(name=member_name, limit=10)

        infos, bills, careers, votes = await asyncio.gather(
            info_task, bills_task, careers_task, votes_task
        )

        basic_info = infos[0] if infos else {"HG_NM": member_name, "note": "기본 정보를 찾을 수 없습니다."}

        # 2. 위원회 경력 기간 분석 (개월 수 계산)
        committee_durations = {}
        for c in careers:
            comm_name = c.PROFILE_SJ
            # "2024.06.10 ~ 2025.05.02" 또는 "2024.06.10 ~ " 파싱
            dates = c.FRTO_DATE.split("~")
            try:
                start_str = dates[0].strip()
                end_str = dates[1].strip() if len(dates) > 1 and dates[1].strip() else None
                
                from datetime import datetime
                start_dt = datetime.strptime(start_str, "%Y.%m.%d")
                end_dt = datetime.strptime(end_str, "%Y.%m.%d") if end_str else datetime.now()
                
                # 개월 수 계산
                months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
                if months < 1: months = 1 # 최소 1개월
                
                committee_durations[comm_name] = committee_durations.get(comm_name, 0) + months
            except Exception:
                continue

        # 3. 통계 요약 생성
        # 상위 3개 전문 위원회 추출
        sorted_expert = sorted(committee_durations.items(), key=lambda x: x[1], reverse=True)
        expertise = [f"{name}({months}개월)" for name, months in sorted_expert[:3]]

        summary_stats = {
            "total_bills_proposed_22nd": len(bills),
            "expertise_areas": expertise,
            "recent_votes_tracked": len(votes),
        }

        return MemberActivityReport(
            member_name=member_name,
            basic_info=basic_info,
            recent_bills=bills,
            committee_careers=careers,
            recent_votes=votes,
            summary_stats=summary_stats
        )

    async def get_bill_voting_results(self, bill_id: str) -> dict[str, Any]:
        """
        특정 의안에 대한 본회의 표결 결과 및 상세 내역을 조회합니다.
        """
        summary = await self.bill_service.get_bill_voting_summary(bill_id)
        if not summary:
            return {"bill_id": bill_id, "message": "해당 의안의 본회의 표결 정보를 찾을 수 없습니다."}

        # 정당별 찬반 경향 파악을 위해 표결 기록 일부 가져오기 (샘플링)
        records = await self.bill_service.get_member_voting_history(bill_id=bill_id, limit=100)

        party_stats = {}
        for r in records:
            p_name = r.POLY_NM or "무소속"
            if p_name not in party_stats:
                party_stats[p_name] = {"찬성": 0, "반대": 0, "기권": 0}

            if "찬성" in r.RESULT_VOTE_MOD:
                party_stats[p_name]["찬성"] += 1
            elif "반대" in r.RESULT_VOTE_MOD:
                party_stats[p_name]["반대"] += 1
            else:
                party_stats[p_name]["기권"] += 1

        return {
            "voting_summary": summary.model_dump(exclude_none=True),
            "party_trend_sample": party_stats,
            "note": "party_trend_sample은 상위 100명의 데이터를 기반으로 한 참고용 통계입니다."
        }

    async def analyze_voting_trends(self, topic: str) -> dict[str, Any]:
        """
        특정 주제와 관련된 법안들의 투표 경향을 분석합니다.
        """
        bills = await self.bill_service.search_bills(keyword=topic, limit=10)

        results = []
        for b in bills:
            if b.PROC_STATUS in ["의결", "본회의 심의"]:
                summary = await self.bill_service.get_bill_voting_summary(b.BILL_ID)
                if summary:
                    results.append(summary.model_dump(exclude_none=True))

        return {
            "topic": topic,
            "analyzed_bills_count": len(results),
            "voting_summaries": results
        }
