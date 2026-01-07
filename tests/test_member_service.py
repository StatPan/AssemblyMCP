from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assemblymcp.services import MemberService


@pytest.mark.asyncio
async def test_member_info_filtering():
    """의원 성명 검색 시 공백 제거 및 필터링 로직 테스트"""
    mock_client = MagicMock()
    # 실제 API 구조 시뮬레이션: {"서비스ID": [{"head": [...]}, {"row": [...]}]}
    mock_data = {
        "OWSSC6001134T516707": [
            {"head": [{"list_total_count": 2}, {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상"}}]},
            {"row": [{"HG_NM": "홍 길 동", "POLY_NM": "A당"}, {"HG_NM": "김철수", "POLY_NM": "B당"}]},
        ]
    }

    with patch("assemblymcp.services._get_data_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = mock_data
        service = MemberService(mock_client)

        # 1. 공백이 포함된 이름으로 검색
        results = await service.get_member_info("홍길동")
        assert len(results) == 1
        assert "홍 길 동" in results[0]["HG_NM"]

        # 2. 검색 결과가 없는 경우 원본 반환 (기존 로직 유지 확인)
        results = await service.get_member_info("이영희")
        assert len(results) == 2


@pytest.mark.asyncio
async def test_member_committee_careers_parsing():
    """의원 경력 데이터 파싱 테스트"""
    mock_client = MagicMock()
    # ORNDP7000993P115502
    mock_data = {
        "ORNDP7000993P115502": [
            {"head": [{"list_total_count": 1}]},
            {"row": [{"HG_NM": "홍길동", "PROFILE_SJ": "법제사법위원회 위원", "FRTO_DATE": "2024.06.10 ~"}]},
        ]
    }

    with patch("assemblymcp.services._get_data_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = mock_data
        service = MemberService(mock_client)
        careers = await service.get_member_committee_careers("홍길동")

        assert len(careers) == 1
        assert careers[0].HG_NM == "홍길동"
        assert "2024.06.10" in careers[0].FRTO_DATE
