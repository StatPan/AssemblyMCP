# AssemblyMCP

대한민국 국회 정보공개 OpenAPI를 MCP(Model Context Protocol) 도구로 제공하는 서버입니다.
LLM 클라이언트가 의안, 의원, 위원회, 회의, 표결, 국회 보고서 데이터를 조회하고 검증형 워크플로로 조합할 수 있게 합니다.

[English README](README_EN.md)

## 먼저 호출할 도구

LLM 클라이언트는 세션 시작 시 `get_legislative_research_kit()`을 먼저 호출하는 것을 권장합니다.
이 도구는 공개 도구 목록, 네이밍 규칙, 권장 워크플로, 실패 마커 계약을 구조화 데이터로 반환합니다.

실패 마커는 다음 형태로 반환됩니다.

| Marker | 의미 |
| --- | --- |
| `[NOT_FOUND]` | 실제 조회했지만 일치 데이터가 없음 |
| `[AMBIGUOUS]` | 후보가 여러 개라 사용자가 식별자를 좁혀야 함 |
| `[VERIFY_FAILED]` | 데이터는 찾았지만 기대 필드와 불일치 |
| `[API_FAILED]` | 국회 API 또는 서버 호출 중 오류 |
| `[PARTIAL]` | 복합 워크플로 일부 단계 실패, 나머지는 사용 가능 |

## 워크플로 중심 도구

| Tool | 목적 |
| --- | --- |
| `verify_legislative_claims(citations_or_text, age="22", limit=5)` | 의안, 의원, 위원회, 표결 주장/인용을 국회 데이터로 검증 |
| `issue_brief(topic, age="22", limit=5)` | 주제별 의안, 위원회, 회의, 보고서, 표결 신호를 통합 |
| `bill_timeline(bill_id, age=None)` | 의안의 발의, 회부, 회의, 표결, 최종 처리 이벤트를 정규화 |
| `legislative_impact_map(target, target_type="auto", age="22", limit=5)` | 주제 또는 의안 중심 관계 그래프(nodes/edges/mermaid) 생성 |
| `watch_action_plan(topic, age="22", limit=5)` | 지속 모니터링을 위한 후속 MCP 호출 계획 생성 |

### 검증 입력 예시

```json
[
  {"type": "bill", "value": "PRC_SAMPLE", "expected": {"status": "위원회 심사"}},
  {"type": "member", "value": "홍길동"},
  {"type": "committee", "value": "법제사법위원회"},
  {"type": "vote", "bill_id": "PRC_SAMPLE", "expected": {"yes": 180}}
]
```

JSON이 아닌 일반 텍스트를 넣으면 `auto` claim으로 처리되어 의안, 의원, 위원회 후보를 순차 확인합니다.

## 조회 및 분석 도구

| Tool | 목적 |
| --- | --- |
| `search_bills(...)` | 키워드, 의안 ID, 발의자, 처리상태 등으로 의안 검색 |
| `get_bill_details(bill_id, age=None)` | 의안 상세, 주요 내용, 제안 이유 조회 |
| `get_bill_history(bill_id)` | 기존 호환용 의안 이력 타임라인 |
| `analyze_legislative_issue(topic, limit=5)` | 주제별 기존 종합 분석 |
| `get_legislative_reports(keyword, limit=5)` | NABO 보고서와 국회 뉴스 검색 |
| `get_committee_work_summary(committee_name)` | 위원회별 계류 의안과 보고서 요약 |
| `get_member_info(name)` | 국회의원 인적사항 검색 |
| `get_representative_report(member_name)` | 의원 기본 정보, 발의 법안, 위원회 경력, 표결 이력 통합 |
| `search_meetings(...)` | 의안 또는 위원회 기준 회의 검색 |
| `get_plenary_schedule(unit_cd=None, page=1, limit=10)` | 본회의 일정 조회 |
| `get_committee_info(...)` | 위원회 목록, 위원회 상세, 위원 명단 조회 |
| `get_bill_voting_results(bill_id)` | 의안별 본회의 표결 결과와 정당별 샘플 경향 |
| `analyze_voting_trends(topic)` | 주제별 표결 경향 분석 |
| `get_member_voting_history(...)` | 의원 또는 의안 기준 개별 표결 기록 |

## Raw API 탐색 도구

AssemblyMCP는 고수준 도구에 없는 데이터도 국회 OpenAPI 메타데이터를 통해 직접 탐색할 수 있습니다.

| Tool | 목적 |
| --- | --- |
| `list_api_services(keyword="")` | 사용 가능한 국회 API 서비스 검색 |
| `get_api_spec(service_id)` | 서비스 파라미터, 응답 구조, 샘플 데이터 확인 |
| `call_api_raw(service_id, params="{}")` | 특정 OpenAPI 서비스 직접 호출 |
| `get_api_code_guide()` | `UNIT_CD`, 처리상태 코드 등 공통 코드 확인 |
| `get_assembly_info()` | 서버 상태와 사용 가이드 확인 |
| `ping()` | 서버 생존 확인 |

권장 탐색 순서:

```text
list_api_services(keyword) -> get_api_spec(service_id) -> call_api_raw(service_id, params)
```

## 빠른 시작

### 1. API 키 발급

[공공데이터포털(data.go.kr)](https://www.data.go.kr/)에서 국회사무처 관련 API 활용 신청 후 인증키를 발급받습니다.

### 2. Claude Desktop 설정

Claude Desktop 설정 파일에 다음 항목을 추가합니다.

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "assembly": {
      "command": "uvx",
      "args": ["git+https://github.com/StatPan/AssemblyMCP"],
      "env": {
        "ASSEMBLY_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

설정 후 Claude Desktop을 재시작합니다.

### 3. 로컬 실행

```bash
export ASSEMBLY_API_KEY="your_api_key_here"
uvx git+https://github.com/StatPan/AssemblyMCP
```

Streamable HTTP 모드로 실행하려면:

```bash
export ASSEMBLY_API_KEY="your_api_key_here"
export MCP_TRANSPORT=http
export MCP_PORT=8000
export MCP_PATH=/mcp
uvx git+https://github.com/StatPan/AssemblyMCP
```

## 개발

### 요구사항

- Python 3.12 이상
- [uv](https://github.com/astral-sh/uv)

### 설치 및 테스트

```bash
git clone https://github.com/StatPan/AssemblyMCP.git
cd AssemblyMCP
uv sync

export ASSEMBLY_API_KEY="your_api_key_here"
uv run assemblymcp
```

품질 확인:

```bash
uv run ruff check .
uv run ruff format .
uv run pytest
```

## 환경 변수

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `ASSEMBLY_API_KEY` | 국회 OpenAPI 인증키 | 없음 |
| `ASSEMBLY_LOG_LEVEL` | 로깅 레벨 | `INFO` |
| `ASSEMBLY_LOG_JSON` | JSON 구조화 로깅 | `False` |
| `ASSEMBLY_ENABLE_CACHING` | 인메모리 캐싱 | `False` |
| `ASSEMBLY_CACHE_TTL_SECONDS` | 캐시 TTL | `300` |
| `ASSEMBLY_CACHE_MAX_SIZE` | 최대 캐시 항목 수 | `100` |
| `MCP_TRANSPORT` | `stdio` 또는 `http` | `stdio` |
| `MCP_HOST` | HTTP 바인드 호스트 | `0.0.0.0` |
| `MCP_PORT` | HTTP 포트 | `8000` |
| `MCP_PATH` | HTTP MCP 경로 | `/mcp` |

## 배포

Dockerfile이 포함되어 있으며 Cloud Run, Railway, Fly.io 등에 배포할 수 있습니다.

```bash
gcloud run deploy assembly-mcp \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars ASSEMBLY_API_KEY="your_key",ASSEMBLY_LOG_JSON="true",ASSEMBLY_ENABLE_CACHING="true"
```

HTTP 배포 시 MCP 엔드포인트 기본 경로는 `/mcp`입니다.

## 라이선스

MIT
