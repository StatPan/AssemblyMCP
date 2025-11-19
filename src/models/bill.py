from datetime import date

from pydantic import BaseModel, Field


class Bill(BaseModel):
    """국회의원 발의법률안 데이터 모델 (OK7XM1000938DS17215)"""

    bill_no: str = Field(..., description="의안번호")
    bill_name: str = Field(..., description="의안명")
    propose_dt: date | None = Field(None, description="발의일자 (YYYYMMDD 형식)")
    proposer_gbn_nm: str = Field(..., description="제안자 구분 (의원 또는 위원회)")
    committee_dt: date | None = Field(None, description="회부일자 (YYYYMMDD 형식)")
    proc_result_cd: str | None = Field(None, description="처리결과 코드")
    link_url: str | None = Field(None, description="상세 링크 URL")

    # 원시 API 데이터의 필드명과 모델 필드명을 매핑하는 별칭.
    # 국회 API에서 가져온 데이터를 이 모델로 변환할 때 사용될 수 있습니다.
    model_config = {
        "json_schema_extra": {
            "example": {
                "BILL_NO": "2100001",
                "BILL_NAME": "국가재정법 일부개정법률안",
                "PROPOSE_DT": "20200530",
                "PROPOSER_GBN_NM": "의원",
                "COMMITTEE_DT": "20200601",
                "PROC_RESULT_CD": "2",
                "LINK_URL": "http://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_C0Y0T0T0M0X0A1F0H1P5V7G6R2Q5Z2",
            }
        }
    }
