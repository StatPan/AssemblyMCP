from pydantic import BaseModel, ConfigDict, Field


class Bill(BaseModel):
    """
    국회의안 정보 데이터 모델. 여러 의안 API를 통합하여 제공하는 최종 모델입니다.
    (Integrates basic info, detailed content, and processing status)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "BILL_ID": "PRC_C0Y0T0T0M0X0A1F0H1P5V7G6R2Q5Z2",
                "BILL_NO": "2100001",
                "BILL_NAME": "국가재정법 일부개정법률안",
                "PROPOSER": "홍길동",
                "PROPOSER_KIND_NM": "의원",
                "PROC_STATUS": "위원회 심사",
                "CURR_COMMITTEE": "기획재정위원회",
                "PROPOSE_DT": "2020-05-30",
                "COMMITTEE_DT": "2020-06-01",
                "PROC_DT": None,
                "LINK_URL": "http://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_C0Y0T0T0M0X0A1F0H1P5V7G6R2Q5Z2",
            }
        },
    )

    BILL_ID: str = Field(..., description="의안ID. 의안의 고유 식별자.")
    BILL_NO: str | None = Field(None, description="의안번호. 의안의 숫자 번호.")
    BILL_NAME: str = Field(..., description="의안명. 의안의 전체 이름.")
    PROPOSER: str = Field(..., description="대표 제안자. 의안을 대표로 발의한 국회의원 또는 위원회 이름.")
    PROPOSER_KIND_NM: str = Field(..., description="제안자 구분. '의원' 또는 '위원회'.")
    PROC_STATUS: str = Field(..., description="처리상태. 의안의 현재 처리 단계 (예: 위원회 심사 등).")
    CURR_COMMITTEE: str = Field(..., description="소관위원회. 의안이 소관된 위원회의 이름.")
    PROPOSE_DT: str | None = Field(None, description="제안일자 (YYYY-MM-DD 형식).")
    COMMITTEE_DT: str | None = Field(None, description="회부일자 (YYYY-MM-DD 형식).")
    PROC_DT: str | None = Field(None, description="최종 처리일자 (YYYY-MM-DD 형식).")
    LINK_URL: str = Field(..., description="상세 링크 URL.")

    # Derivations (Keep but with clear naming if helpful, or use uppercase if they exist in some APIs)
    PRIMARY_PROPOSER: str | None = Field(None, description="대표 제안자 이름만 추출한 값.")
    PROPOSER_COUNT: int | None = Field(None, description="총 제안자 수 (추정치).")


class BillDetail(Bill):
    """
    법률안 상세 정보 데이터 모델.
    기본 Bill 정보에 제안이유와 주요내용을 추가합니다.
    """

    MAJOR_CONTENT: str | None = Field(None, description="주요내용 요약.")
    PROPOSE_REASON: str | None = Field(None, description="제안이유.")


class Committee(BaseModel):
    """
    국회 위원회 정보 데이터 모델.
    (Committee Information)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "HR_DEPT_CD": "9700008",
                "COMMITTEE_NAME": "법제사법위원회",
                "CMT_DIV_NM": "상임위원회",
                "HG_NM": "박광온",
                "CURR_CNT": 18,
                "LIMIT_CNT": 18,
            }
        }
    )

    HR_DEPT_CD: str = Field(..., alias="committee_code", description="위원회 코드.")
    COMMITTEE_NAME: str = Field(..., description="위원회명.")
    CMT_DIV_NM: str | None = Field(None, description="위원회 구분. 예: 상임위원회, 특별위원회.")
    HG_NM: str | None = Field(None, description="위원장 이름.")
    CURR_CNT: int | None = Field(None, description="현원.")
    LIMIT_CNT: int | None = Field(None, description="정원.")


class LegislativeReport(BaseModel):
    """
    국회 전문 보고서 및 뉴스 데이터 모델.
    """
    source: str = Field(..., description="데이터 출처 (예: 국회예산정책처, 국회뉴스ON)")
    title: str = Field(..., description="보고서 또는 뉴스 제목")
    date: str | None = Field(None, description="발간 또는 등록 일자")
    link: str | None = Field(None, description="상세 원문 링크")
    report_type: str | None = Field(None, description="데이터 유형 (분석보고서, 뉴스 등)")


class CommitteeWorkSummary(BaseModel):
    """
    위원회 활동 현황 통합 모델.
    """
    committee_name: str = Field(..., description="위원회명")
    pending_bills_sample: list[Bill] = Field(default_factory=list, description="현재 계류 중인 주요 의안 샘플")
    related_reports: list[LegislativeReport] = Field(default_factory=list, description="위원회 관련 전문 보고서 및 소식")
    instruction: str | None = Field(None, description="사용자(LLM) 가이드 메시지")


class CommitteePerformanceReport(BaseModel):
    """
    위원회 성과 및 협치 분석 리포트 모델.
    """
    committee_name: str = Field(..., description="위원회명")
    stats: dict = Field(..., description="주요 통계 (가결률, 평균 찬성률 등)")
    passed_bills_analysis: list[dict] = Field(default_factory=list, description="주요 가결 법안 및 표결 분석")
    nabo_fiscal_data: list[LegislativeReport] = Field(default_factory=list, description="관련 예산/경제 분석 보고서")
    consensus_score: float = Field(..., description="협치 지수 (0~100, 찬성률 기반)")
    summary: str = Field(..., description="위원회 활동 총평")


class TopicConsensusReport(BaseModel):
    """
    특정 주제(이슈)에 대한 정당 간 합의 정도 분석 리포트 모델.
    """
    topic: str = Field(..., description="분석 주제")
    overall_consensus_score: float = Field(..., description="평균 찬성률 (합의 수준)")
    analyzed_bills_count: int = Field(..., description="분석된 가결 법안 수")
    bills_detail: list[dict] = Field(default_factory=list, description="각 법안별 표결 현황")
    consensus_trend: str = Field(..., description="합의 경향 분석 메시지")


class VoteRecord(BaseModel):
    """
    개별 국회의원의 본회의 표결 기록 모델.
    """
    BILL_ID: str = Field(..., description="의안 고유 식별자")
    BILL_NAME: str = Field(..., description="의안명")
    VOTE_DATE: str | None = Field(None, description="의결일자 (YYYY-MM-DD)")
    RESULT_VOTE_MOD: str = Field(..., description="표결 결과 (찬성, 반대, 기권)")
    HG_NM: str = Field(..., description="의원 성명")
    POLY_NM: str | None = Field(None, description="소속 정당")


class BillVotingSummary(BaseModel):
    """
    의안별 본회의 표결 통계 요약 모델.
    """
    BILL_ID: str = Field(..., description="의안 고유 식별자")
    BILL_NAME: str = Field(..., description="의안명")
    PROC_DT: str | None = Field(None, description="처리 일자 (YYYY-MM-DD)")
    MEMBER_TCNT: int | None = Field(None, description="재적 의원 수")
    VOTE_TCNT: int | None = Field(None, description="총 투표 수")
    YES_TCNT: int | None = Field(None, description="찬성 수")
    NO_TCNT: int | None = Field(None, description="반대 수")
    BLANK_TCNT: int | None = Field(None, description="기권 수")
    PROC_RESULT_CD: str | None = Field(None, description="의결 결과 (예: 가결, 부결)")


class MemberCommitteeCareer(BaseModel):
    """
    의원의 위원회 활동 경력 모델.
    """
    HG_NM: str = Field(..., description="의원 성명")
    PROFILE_SJ: str = Field(..., description="위원회 경력 명칭")
    FRTO_DATE: str | None = Field(None, description="활동 기간")
    PROFILE_UNIT_NM: str | None = Field(None, description="국회 대수")


class MemberActivityReport(BaseModel):
    """
    국회의원 종합 의정활동 리포트 모델.
    """
    member_name: str = Field(..., description="의원 성명")
    basic_info: dict = Field(..., description="의원 기본 인적사항")
    recent_bills: list[Bill] = Field(default_factory=list, description="최근 대표 발의 법안")
    committee_careers: list[MemberCommitteeCareer] = Field(default_factory=list, description="위원회 활동 경력")
    recent_votes: list[VoteRecord] = Field(default_factory=list, description="최근 본회의 표결 참여 기록")
    summary_stats: dict = Field(default_factory=dict, description="활동 통계 요약")
