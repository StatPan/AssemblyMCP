from pydantic import BaseModel, Field


class Bill(BaseModel):
    """국회의안 정보 데이터 모델."""

    BILL_ID: str = Field(..., description="의안ID")
    BILL_NO: str | None = Field(None, description="의안번호")
    BILL_NAME: str = Field(..., description="의안명")
    PROPOSER: str = Field(..., description="대표 제안자")
    PROPOSER_KIND_NM: str = Field(..., description="제안자 구분")
    PROC_STATUS: str = Field(..., description="처리상태")
    CURR_COMMITTEE: str = Field(..., description="소관위원회")
    PROPOSE_DT: str | None = Field(None, description="제안일자")
    COMMITTEE_DT: str | None = Field(None, description="회부일자")
    PROC_DT: str | None = Field(None, description="최종 처리일자")
    LINK_URL: str = Field(..., description="상세 링크 URL")
    PRIMARY_PROPOSER: str | None = Field(None, description="대표 제안자 이름")
    PROPOSER_COUNT: int | None = Field(None, description="총 제안자 수")


class BillDetail(Bill):
    """법률안 상세 정보."""

    MAJOR_CONTENT: str | None = Field(None, description="주요내용 요약")
    PROPOSE_REASON: str | None = Field(None, description="제안이유")


class Committee(BaseModel):
    """국회 위원회 정보."""

    HR_DEPT_CD: str = Field(..., description="위원회 코드")
    COMMITTEE_NAME: str = Field(..., description="위원회명")
    CMT_DIV_NM: str | None = Field(None, description="위원회 구분")
    HG_NM: str | None = Field(None, description="위원장 이름")
    CURR_CNT: int | None = Field(None, description="현원")
    LIMIT_CNT: int | None = Field(None, description="정원")


class LegislativeReport(BaseModel):
    """국회 전문 보고서 및 뉴스 데이터."""

    source: str = Field(..., description="출처")
    title: str = Field(..., description="제목")
    date: str | None = Field(None, description="등록 일자")
    link: str | None = Field(None, description="상세 링크")
    report_type: str | None = Field(None, description="유형")


class CommitteeWorkSummary(BaseModel):
    """위원회 활동 현황 집계 데이터."""

    committee_name: str = Field(..., description="위원회명")
    pending_bills_sample: list[Bill] = Field(default_factory=list, description="계류 중인 주요 의안")
    related_reports: list[LegislativeReport] = Field(default_factory=list, description="관련 보고서 및 뉴스")


class CommitteeVotingStats(BaseModel):
    """위원회별 투표 수치 집계."""

    committee_name: str = Field(..., description="위원회명")
    assembly_age: str = Field(..., description="분석 대상 국회 대수")
    avg_yes_rate: float = Field(..., description="가결 법안 평균 찬성률")
    total_bills_analyzed: int = Field(..., description="집계 대상 법안 수")
    bills_detail: list[dict] = Field(default_factory=list, description="상세 표결 데이터 목록")


class TopicVotingStats(BaseModel):
    """주제별 투표 수치 집계."""

    keyword: str = Field(..., description="검색 키워드")
    assembly_age: str = Field(..., description="국회 대수")
    avg_yes_rate: float = Field(..., description="평균 찬성률")
    bill_count: int = Field(..., description="집계 대상 법안 수")
    individual_results: list[dict] = Field(default_factory=list, description="개별 투표 결과")


class VoteRecord(BaseModel):
    """개별 의원 표결 기록."""

    BILL_ID: str = Field(..., description="의안 고유 식별자")
    BILL_NAME: str = Field(..., description="의안명")
    VOTE_DATE: str | None = Field(None, description="의결일자")
    RESULT_VOTE_MOD: str = Field(..., description="표결 결과")
    HG_NM: str = Field(..., description="의원 성명")
    POLY_NM: str | None = Field(None, description="소속 정당")


class BillVotingSummary(BaseModel):
    """의안별 본회의 표결 통계 요약."""

    BILL_ID: str = Field(..., description="의안ID")
    BILL_NAME: str = Field(..., description="의안명")
    PROC_DT: str | None = Field(None, description="처리 일자")
    MEMBER_TCNT: int | None = Field(None, description="재적")
    VOTE_TCNT: int | None = Field(None, description="투표")
    YES_TCNT: int | None = Field(None, description="찬성")
    NO_TCNT: int | None = Field(None, description="반대")
    BLANK_TCNT: int | None = Field(None, description="기권")
    PROC_RESULT_CD: str | None = Field(None, description="의결 결과")


class MemberCommitteeCareer(BaseModel):
    """의원 위원회 활동 경력."""

    HG_NM: str = Field(..., description="의원 성명")
    PROFILE_SJ: str = Field(..., description="경력 명칭")
    FRTO_DATE: str | None = Field(None, description="활동 기간")
    PROFILE_UNIT_NM: str | None = Field(None, description="국회 대수")


class MemberActivityReport(BaseModel):
    """의원 종합 활동 집계 데이터."""

    member_name: str = Field(..., description="의원 성명")
    basic_info: dict = Field(..., description="기본 인적사항")
    recent_bills: list[Bill] = Field(default_factory=list, description="최근 대표 발의 법안")
    committee_careers: list[MemberCommitteeCareer] = Field(default_factory=list, description="위원회 경력")
    recent_votes: list[VoteRecord] = Field(default_factory=list, description="최근 표결 참여 기록")
    summary_stats: dict = Field(default_factory=dict, description="활동 수치 요약")
