import os

import httpx
from dotenv import load_dotenv

# settings 모듈이 있을 가능성이 높으므로, settings를 가정하고 작성합니다.
# 실제로는 settings.py 파일의 내용을 확인해야 하지만, 흐름상 가정하고 진행합니다.


class AssemblyAPIClient:
    """국회 공공데이터 API 호출을 위한 기본 클라이언트."""

    BASE_URL = "https://open.assembly.go.kr/portal/openapi"  # HTTPS로 수정

    def __init__(self, api_key: str = None):
        # settings 모듈이 없을 경우를 대비하여 환경 변수를 직접 로드하고 가져옵니다.
        load_dotenv()
        self.api_key = api_key or os.getenv("ASSEMBLY_API_KEY")

        if not self.api_key:
            raise ValueError("ASSEMBLY_API_KEY가 설정되지 않았습니다.")

        # HTTPS 리디렉션 문제를 해결하기 위해 BASE_URL을 HTTPS로 변경하고
        # follow_redirects=True를 명시합니다.
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=10.0, follow_redirects=True)

    async def get_data(self, service_id: str, params: dict = None):
        """
        특정 서비스 ID의 API를 호출하여 데이터를 가져옵니다.

        API의 공통 규격:
        - KEY: 인증키
        - pIndex: 페이지 번호
        - pSize: 페이지당 건수
        - AGE: 국회 대수
        """

        # 최종 API 호출 구조 추정: /json/서비스ID 형태로 URL 경로를 구성하고
        # Type 파라미터를 제거합니다.
        default_params = {
            "KEY": self.api_key,
            "pIndex": 1,
            "pSize": 100,  # 기본 100건 설정
        }

        # URL 경로에 서비스 ID와 JSON 타입을 포함 (최종 시도)
        url_path = f"/{service_id}/json"

        merged_params = {**default_params, **(params or {})}

        try:
            response = await self.client.get(url_path, params=merged_params)
            response.raise_for_status()

            # 국회 API의 특성상 JSON 구조가 중첩되어 있을 수 있습니다.
            # 여기서는 일단 전체 JSON을 반환하고 상위 로직에서 처리하도록 합니다.
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP 오류 발생: {e.response.status_code} - {e.response.text}")
            # GH_ISSUE_01.md에서 언급된 404/ERROR-310 오류 처리
            if e.response.status_code == 404 or "ERROR-310" in e.response.text:
                # TODO: API 호출 URL 및 파라미터 조합 테스트 필요
                raise ConnectionError(
                    "API 호출 URL 또는 파라미터 조합 오류 가능성 확인 필요."
                ) from e
            raise
        except Exception as e:
            print(f"API 호출 중 예외 발생: {e}")
            raise
