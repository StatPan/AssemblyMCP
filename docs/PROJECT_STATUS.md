# AssemblyMCP Project Status

이 문서는 현재 워크트리 상태, 최근 변경 방향, 다음 작업 우선순위를 빠르게 파악하기 위한 운영 메모입니다.

## Current Status

- 기준 시점: 2026-04-01
- 개발 상태: 실행 가능, 핵심 테스트 통과
- 현재 작업 브랜치: `refactor/pydantic-model-first`
- 핵심 연동 상태: `assembly-api-client` `v1.2.6` 계약 반영 완료

## Verified State

- `AssemblyMCP`: `uv run pytest -q` -> `67 passed`
- `assembly-api-client`: `uv run pytest -q` -> `254 passed`
- 실데이터 스모크 확인 완료:
  - 최근 법안 조회
  - 의원 정보 조회
  - 위원회 일정 조회
  - 위원회 목록 조회

## Recent Technical Changes

- `assembly-api-client>=1.2.6`로 의존성 상향
- `get_data()`의 반환 계약 변경 반영
  - 과거: 중첩된 raw dict 중심 응답
  - 현재: `list[BaseModel]` 또는 `list[dict]`
- `assemblymcp/services.py`에서 `_collect_rows()`로 응답 평탄화 통일
- 관련 테스트 전반을 새 계약 기준으로 정리

## Operational Notes

- `.env`의 `ASSEMBLY_API_KEY` 설정 시 실 API 호출 가능
- `assemblymcp/config.py` 설정 필드는 `assembly_api_key`가 아니라 `api_key`
- `MeetingService.search_meetings()`는 `page_size`가 아니라 `limit` 인자를 사용

## Remaining Workspace Notes

- 이 저장소에는 코드 미완료 흔적이 거의 없음
- 별도 저장소 `assembly-api-client`에는 `uv.lock` 수정이 남아 있음
- 이 저장소의 `.agent/` 메모는 이 문서로 통합함

## Suggested Next Steps

1. `assembly-api-client`의 `uv.lock` 변경을 유지할지 결정
2. 필요하면 Docker 빌드/런타임 검증 추가
3. 배포 전 실제 사용 시나리오 기준 스모크 스크립트 정리
4. 운영 문서가 더 필요하면 `docs/HANDOVER_GUIDE.md`와 역할 분리 유지
