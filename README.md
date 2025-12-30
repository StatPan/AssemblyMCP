# AssemblyMCP

대한민국 국회 정보공개 시스템(Open API)을 위한 MCP(Model Context Protocol) 서버입니다.
Claude와 같은 AI 에이전트가 국회의 의안, 회의록, 의원 정보 등을 실시간으로 조회하고 분석할 수 있게 해줍니다.

[English README is available here](README_EN.md)

---

## 주요 기능

이 서버는 다음과 같은 도구(Tools)를 제공합니다:

*   **의안 검색 및 조회**
    *   `search_bills(keyword)`: 키워드로 의안을 검색합니다. (예: "인공지능", "예산")
    *   `get_recent_bills()`: 최근 발의된 의안 목록을 가져옵니다.
    *   `get_bill_details(bill_id)`: 의안의 상세 내용(제안 이유, 주요 골자 등)을 조회합니다.
    *   `get_bill_info(...)`: 의안 번호, 발의자, 날짜 등 상세 조건으로 의안을 검색합니다.

*   **회의록 및 위원회**
    *   `get_meeting_records(bill_id)`: 특정 의안과 관련된 위원회 회의록을 조회합니다.
    *   `search_meetings(...)`: 날짜, 위원회명 등으로 회의록을 검색합니다.
    *   `get_committee_list()`: 국회 위원회 목록을 조회합니다.
    *   `get_committee_members(...)`: 위원회 구성원(위원 명단)을 조회합니다.

*   **국회의원 정보**
    *   `get_member_info(name)`: 국회의원의 인적 사항, 소속 정당, 지역구 등을 조회합니다.
    *   `get_representative_report(name)`: **[지능형]** 의원의 기본 정보, 발의 법안, 위원회 경력, 투표 이력을 통합한 종합 리포트를 생성합니다.
    *   `get_member_committee_careers(name)`: 의원의 상세 위원회 활동 경력을 조회합니다.

*   **표결 및 투표 분석**
    *   `get_bill_voting_results(bill_id)`: **[지능형]** 특정 의안의 본회의 표결 결과(찬성/반대/기권)와 정당별 투표 경향을 분석합니다.
    *   `analyze_voting_trends(topic)`: **[지능형]** 특정 주제(예: "AI", "세제") 관련 법안들의 본회의 투표 성향을 분석합니다.
    *   `get_member_voting_history(...)`: 특정 의원 또는 의안의 개별 표결 기록을 조회합니다.

*   **지능형 분석 및 복합 조회**
    *   `analyze_legislative_issue(topic)`: **[지능형]** 특정 주제에 대한 법안, 회의록, 주요 의원을 통합 분석하여 리포트를 생성합니다.
    *   `get_bill_history(bill_id)`: **[지능형]** 의안의 발의부터 처리까지의 전 생애주기를 타임라인 형태로 통합 제공합니다.
    *   `get_legislative_reports(keyword)`: **[지능형]** 국회예산정책처(NABO) 전문 보고서 및 국회 뉴스 데이터를 실시간 연계하여 제공합니다.
    *   `get_committee_work_summary(committee_name)`: **[지능형]** 위원회별 계류 의안과 관련 보고서를 통합하여 현황을 요약합니다.

*   **기타 및 고급 기능**
    *   `get_assembly_info()`: 서버 상태 및 사용 가능한 API 정보를 확인합니다.
    *   `list_api_services()`: 사용 가능한 모든 국회 API 서비스를 검색합니다.
    *   `call_api_raw()`: (고급 사용자용) API 서비스를 직접 호출합니다.

## LLM 사용 가이드 (중요)

- 이 서버는 국회 OpenAPI **약 270개**를 모두 사용할 수 있습니다. 고수준 툴에 없다고 해서 “기능이 없다”라고 답하지 마세요.
- **지능형 워크플로우 우선 사용**: 단순히 데이터를 나열하기보다 `analyze_` 또는 `get_..._report` 계열의 도구를 사용하여 입체적인 인사이트를 제공하세요.
    - **주제 분석**: `analyze_legislative_issue("AI")` -> 법안 + 회의 + 의원 통합 정보
    - **의원 분석**: `get_representative_report("의원명")` -> 인적사항 + 법안 + 경력 + 투표성향
    - **의결 분석**: `get_bill_voting_results("의안ID")` -> 찬반 통계 + 정당별 경향
- **표준 가이드**: `list_api_services(keyword)` → `get_api_spec(service_id)` → `call_api_raw(service_id, params)` 조합으로 어떤 정보든 조회할 수 있습니다.
- 키워드는 넓게 검색하세요(국문/영문, 띄어쓰기 변형). 찾은 ID는 `get_api_spec`으로 필수 파라미터를 확인한 뒤 `call_api_raw`로 호출합니다.
- 예시: “위원회 구성원” → `list_api_services("위원 명단")`에서 서비스 ID 확인 → `get_api_spec`으로 파라미터 확인 → `call_api_raw`로 명단 조회 → 필요 시 `get_member_info`로 개별 의원 상세를 보강.
- 답변 시: 고수준 툴에 없으면 위 조합을 제안하거나 직접 호출해 결과를 만들어 주세요.
- 빠른 길: 위원 명단은 `get_committee_members`로 바로 조회할 수 있으며, 후속으로 `get_member_info`로 상세를 붙이면 됩니다.

---

## 시작하기 (Quick Start)

이 프로젝트는 `uv` 패키지 매니저를 기반으로 관리되며, `uvx`를 통해 설치 없이 바로 실행할 수 있습니다.

### 1. API 키 발급
[공공데이터포털(data.go.kr)](https://www.data.go.kr/)에서 '국회사무처' 관련 API 활용 신청을 하여 인증키를 발급받으세요.

### 2. Claude Desktop 연동 설정

Claude Desktop 앱에서 이 MCP 서버를 사용하려면 설정 파일을 수정해야 합니다.

1.  설정 파일 열기:
    *   **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
    *   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2.  아래 내용을 추가하세요. (`your_api_key_here` 부분에 발급받은 키를 입력)

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

3.  Claude Desktop을 재시작하면 🔌 아이콘과 함께 AssemblyMCP 도구들을 사용할 수 있습니다.

### 3. 서버 직접 실행 (테스트용)

LLM 연동 없이 서버가 정상적으로 작동하는지 터미널에서 테스트할 수 있습니다.

```bash
# API 키 설정 (Linux/macOS)
export ASSEMBLY_API_KEY="your_api_key_here"

# 서버 실행
# GitHub에서 최신 코드를 받아와 실행합니다.
uvx git+https://github.com/StatPan/AssemblyMCP
```

---

## 개발 가이드

이 프로젝트에 기여하거나 로컬에서 수정하여 실행하려면 다음 단계를 따르세요.

### 필수 요구사항
- Python 3.12 이상
- [uv](https://github.com/astral-sh/uv) 패키지 매니저

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/StatPan/AssemblyMCP.git
cd AssemblyMCP

# 2. 의존성 설치
uv sync

# 3. 환경 변수 설정 (.env 파일 생성)
cp .env.example .env
# .env 파일을 열어 ASSEMBLY_API_KEY를 입력하세요.

# 4. 개발 서버 실행
uv run assemblymcp
```

### 코드 품질 관리
```bash
# 린트 및 포맷팅
uv run ruff check .
uv run ruff format .

# 테스트 실행
uv run pytest
```

## 라이선스

MIT

---

## 설정 및 호스팅 (Configuration & Hosting)

AssemblyMCP는 **"Battery-Included"** 아키텍처를 채택하여, 별도의 코드 수정 없이 환경변수만으로 로깅, 캐싱 등 운영 기능을 제어할 수 있습니다.

### 환경 변수 설정 (Environment Variables)

| 변수명 | 설명 | 기본값 | 예시 |
| :--- | :--- | :--- | :--- |
| `ASSEMBLY_API_KEY` | **[필수]** 국회 OpenAPI 인증키 | - | `1234abcd...` |
| `ASSEMBLY_LOG_LEVEL` | 로깅 레벨 (DEBUG, INFO, WARNING, ERROR) | `INFO` | `DEBUG` |
| `ASSEMBLY_LOG_JSON` | JSON 구조화 로깅 활성화 (Cloud Run 등 운영 환경용) | `False` | `True` |
| `ASSEMBLY_ENABLE_CACHING` | 인메모리 캐싱 활성화 (조회 성능 향상) | `False` | `True` |
| `ASSEMBLY_CACHE_TTL_SECONDS` | 캐시 유지 시간 (초) | `300` (5분) | `600` |
| `ASSEMBLY_CACHE_MAX_SIZE` | 최대 캐시 항목 수 | `100` | `500` |

### 운영 모드 (Production Mode)

Cloud Run, AWS Lambda 등 서버리스 환경이나 프로덕션 배포 시에는 다음 설정을 권장합니다.

```bash
# JSON 로깅 활성화 (로그 수집기 파싱 용이)
export ASSEMBLY_LOG_JSON=true

# 캐싱 활성화 (API 호출 비용 절감 및 속도 향상)
export ASSEMBLY_ENABLE_CACHING=true
```

## 배포 (Deployment)

이 서버는 Docker를 사용하여 Google Cloud Run, Railway, Fly.io 등 클라우드 플랫폼에 쉽게 배포할 수 있습니다.

### Docker 배포

1. **Dockerfile**이 포함되어 있어 별도 설정 없이 바로 빌드할 수 있습니다.
2. 배포 시 `ASSEMBLY_API_KEY` 등 필요한 환경 변수를 설정하세요.
3. 서버는 기본적으로 `Streamable HTTP` 모드로 실행되며 `8000` 포트를 사용합니다.

### Google Cloud Run 배포 예시

```bash
gcloud run deploy assembly-mcp \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars ASSEMBLY_API_KEY="your_key",ASSEMBLY_LOG_JSON="true",ASSEMBLY_ENABLE_CACHING="true"
```

### 주요 변경사항

- **Streamable HTTP Transport**: MCP 프로토콜의 최신 표준인 Streamable HTTP를 사용합니다.
- **엔드포인트**: `/mcp` 경로에서 MCP 서버가 실행됩니다.

