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

*   **기타 및 고급 기능**
    *   `get_assembly_info()`: 서버 상태 및 사용 가능한 API 정보를 확인합니다.
    *   `list_api_services()`: 사용 가능한 모든 국회 API 서비스를 검색합니다.
    *   `call_api_raw()`: (고급 사용자용) API 서비스를 직접 호출합니다.

## LLM 사용 가이드 (중요)

- 이 서버는 국회 OpenAPI **약 270개**를 모두 사용할 수 있습니다. 고수준 툴에 없다고 해서 “기능이 없다”라고 답하지 마세요.
- 기본 전략: `list_api_services(keyword)` → `get_api_spec(service_id)` → `call_api_raw(service_id, params)` 조합으로 어떤 정보든 조회할 수 있습니다.
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

## 배포 (Deployment)

이 서버는 Docker를 사용하여 Railway, Render, Fly.io 등 클라우드 플랫폼에 쉽게 배포할 수 있습니다.

### Docker 배포

1. **Dockerfile**이 포함되어 있어 별도 설정 없이 바로 빌드할 수 있습니다.
2. 배포 시 환경 변수 `ASSEMBLY_API_KEY`를 반드시 설정해야 합니다.
3. 서버는 기본적으로 `SSE` 모드(`MCP_TRANSPORT=sse`)로 실행되며 `8000` 포트를 사용합니다.

### Railway 배포 예시

1. GitHub 리포지토리를 Railway에 연결합니다.
2. Variables 설정에서 `ASSEMBLY_API_KEY`를 추가합니다.
3. 자동으로 Dockerfile을 감지하여 빌드 및 배포됩니다.
4. 생성된 URL (예: `https://assembly-mcp.up.railway.app`) 뒤에 `/mcp`를 붙여 MCP 클라이언트에 등록합니다.
   - MCP Server URL: `https://assembly-mcp.up.railway.app/mcp`

### 주요 변경사항

- **Streamable HTTP Transport**: MCP 프로토콜의 최신 표준인 Streamable HTTP를 사용합니다 (SSE는 deprecated).
- **엔드포인트**: `/mcp` 경로에서 MCP 서버가 실행됩니다.
- **환경 변수**: `MCP_TRANSPORT=http`, `MCP_PATH=/mcp`로 설정됩니다.
