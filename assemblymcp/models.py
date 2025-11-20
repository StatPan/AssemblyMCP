from datetime import date

from pydantic import BaseModel, Field


class Bill(BaseModel):
    """
    국회의안 정보 데이터 모델. 여러 의안 API를 통합하여 제공하는 최종 모델입니다.
    (Integrates basic info, detailed content, and processing status)
    """

    bill_id: str = Field(..., description="의안ID (BILL_ID/BILL_NO). 의안의 고유 식별자.")
    bill_name: str = Field(..., description="의안명 (BILL_NAME). 의안의 전체 이름.")
    proposer: str = Field(
        ..., description="대표 제안자 (PROPOSER). 의안을 대표로 발의한 국회의원 또는 위원회 이름."
    )
    proposer_kind_name: str = Field(
        ..., description="제안자 구분 (PROPOSER_KIND). '의원' 또는 '위원회'."
    )
    proc_status: str = Field(
        ..., description="처리상태 (PROC_STATUS). 의안의 현재 처리 단계 (예: 위원회 심사 등)."
    )
    committee: str = Field(..., description="소관위원회 (COMMITTEE). 의안이 소관된 위원회의 이름.")
    propose_dt: date = Field(
        ..., description="제안일자 (PROPOSE_DT). 의안이 발의된 날짜 (YYYYMMDD 형식)."
    )
    committee_dt: date | None = Field(
        None, description="회부일자 (COMMITTEE_DT). 위원회에 회부된 날짜 (YYYYMMDD 형식)."
    )
    proc_dt: date | None = Field(
        None, description="최종 처리일자 (PROC_DT). 의안이 최종 처리된 날짜 (YYYYMMDD 형식)."
    )
    link_url: str = Field(..., description="상세 링크 URL (LINK_URL). 국회 의안정보시스템.")

    # 원시 API 데이터의 필드명과 모델 필드명을 매핑하는 별칭.
    # 국회 API에서 가져온 데이터를 이 모델로 변환할 때 사용될 수 있습니다.
    model_config = {
        "json_schema_extra": {
            "example": {
                "bill_id": "2100001",
                "bill_name": "국가재정법 일부개정법률안",
                "proposer": "홍길동",
                "proposer_kind_name": "의원",
                "proc_status": "위원회 심사",
                "committee": "기획재정위원회",
                "propose_dt": "2020-05-30",
                "committee_dt": "2020-06-01",
                "proc_dt": None,
                "link_url": "http://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_C0Y0T0T0M0X0A1F0H1P5V7G6R2Q5Z2",
            }
        }
    }
