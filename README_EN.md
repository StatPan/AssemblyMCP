# AssemblyMCP

AssemblyMCP is an MCP (Model Context Protocol) server for the Korean National Assembly Open API.
It lets LLM clients retrieve, verify, and combine data about bills, members, committees, meetings, votes, and National Assembly reports.

[Korean README](README.md)

## First Tool To Call

LLM clients should start a session with `get_legislative_research_kit()`.
It returns the public tool surface, naming rules, recommended workflows, and stable failure marker contract.

Failure markers:

| Marker | Meaning |
| --- | --- |
| `[NOT_FOUND]` | The server queried real data but found no matching row |
| `[AMBIGUOUS]` | Multiple candidates matched and the user should narrow the identifier |
| `[VERIFY_FAILED]` | A row was found, but expected fields did not match Assembly data |
| `[API_FAILED]` | The Assembly API or server call failed |
| `[PARTIAL]` | A composite workflow step failed, but remaining sections are usable |

## Workflow Tools

| Tool | Purpose |
| --- | --- |
| `verify_legislative_claims(citations_or_text, age="22", limit=5)` | Verify bill, member, committee, and vote claims against Assembly data |
| `issue_brief(topic, age="22", limit=5)` | Combine bills, committees, meetings, reports, and voting signals for an issue |
| `bill_timeline(bill_id, age=None)` | Normalize bill introduction, referral, meeting, vote, and disposition events |
| `legislative_impact_map(target, target_type="auto", age="22", limit=5)` | Build a graph of related bills, committees, members, reports, and votes |
| `watch_action_plan(topic, age="22", limit=5)` | Produce a monitoring plan and next MCP calls for a legislative topic |

Example verification input:

```json
[
  {"type": "bill", "value": "PRC_SAMPLE", "expected": {"status": "Committee review"}},
  {"type": "member", "value": "Hong Gil-dong"},
  {"type": "committee", "value": "Legislation and Judiciary Committee"},
  {"type": "vote", "bill_id": "PRC_SAMPLE", "expected": {"yes": 180}}
]
```

Plain text input is treated as an `auto` claim and checked against bill, member, and committee candidates.

## Lookup And Analysis Tools

| Tool | Purpose |
| --- | --- |
| `search_bills(...)` | Search bills by keyword, bill ID, proposer, status, and related filters |
| `get_bill_details(bill_id, age=None)` | Retrieve bill details, major content, and proposal reason |
| `get_bill_history(bill_id)` | Compatibility bill history timeline |
| `analyze_legislative_issue(topic, limit=5)` | Existing topic-level composite analysis |
| `get_legislative_reports(keyword, limit=5)` | Search NABO reports and National Assembly news |
| `get_committee_work_summary(committee_name)` | Summarize committee pending bills and related reports |
| `get_member_info(name)` | Search National Assembly member profile data |
| `get_representative_report(member_name)` | Combine member profile, bills, committee careers, and voting history |
| `search_meetings(...)` | Search meetings by bill or committee |
| `get_plenary_schedule(unit_cd=None, page=1, limit=10)` | Retrieve plenary schedules |
| `get_committee_info(...)` | Retrieve committee list, details, and roster |
| `get_bill_voting_results(bill_id)` | Retrieve plenary voting result and party trend sample |
| `analyze_voting_trends(topic)` | Analyze voting trends for a topic |
| `get_member_voting_history(...)` | Retrieve individual vote records by member or bill |

## Raw API Discovery Tools

AssemblyMCP can reach data that is not wrapped by high-level tools through the raw API discovery flow.

| Tool | Purpose |
| --- | --- |
| `list_api_services(keyword="")` | Search available National Assembly API services |
| `get_api_spec(service_id)` | Inspect parameters, response shape, and sample data |
| `call_api_raw(service_id, params="{}")` | Directly call a specific OpenAPI service |
| `get_api_code_guide()` | Inspect shared codes such as `UNIT_CD` and process status values |
| `get_assembly_info()` | Retrieve server status and usage guide |
| `ping()` | Health check |

Recommended discovery path:

```text
list_api_services(keyword) -> get_api_spec(service_id) -> call_api_raw(service_id, params)
```

## Quick Start

### 1. Get An API Key

Get an API key from [data.go.kr](https://www.data.go.kr/) for APIs provided by the National Assembly Secretariat.

### 2. Claude Desktop Configuration

Add this server to your Claude Desktop configuration file.

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

Restart Claude Desktop after editing the configuration.

### 3. Run Locally

```bash
export ASSEMBLY_API_KEY="your_api_key_here"
uvx git+https://github.com/StatPan/AssemblyMCP
```

Run with Streamable HTTP:

```bash
export ASSEMBLY_API_KEY="your_api_key_here"
export MCP_TRANSPORT=http
export MCP_PORT=8000
export MCP_PATH=/mcp
uvx git+https://github.com/StatPan/AssemblyMCP
```

## Development

### Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

### Setup And Test

```bash
git clone https://github.com/StatPan/AssemblyMCP.git
cd AssemblyMCP
uv sync

export ASSEMBLY_API_KEY="your_api_key_here"
uv run assemblymcp
```

Quality checks:

```bash
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `ASSEMBLY_API_KEY` | National Assembly OpenAPI key | none |
| `ASSEMBLY_LOG_LEVEL` | Logging level | `INFO` |
| `ASSEMBLY_LOG_JSON` | JSON structured logging | `False` |
| `ASSEMBLY_ENABLE_CACHING` | In-memory caching | `False` |
| `ASSEMBLY_CACHE_TTL_SECONDS` | Cache TTL | `300` |
| `ASSEMBLY_CACHE_MAX_SIZE` | Maximum cache entries | `100` |
| `MCP_TRANSPORT` | `stdio` or `http` | `stdio` |
| `MCP_HOST` | HTTP bind host | `0.0.0.0` |
| `MCP_PORT` | HTTP port | `8000` |
| `MCP_PATH` | HTTP MCP path | `/mcp` |

## Deployment

The repository includes a Dockerfile and can be deployed to Cloud Run, Railway, Fly.io, or similar platforms.

```bash
gcloud run deploy assembly-mcp \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars ASSEMBLY_API_KEY="your_key",ASSEMBLY_LOG_JSON="true",ASSEMBLY_ENABLE_CACHING="true"
```

The default HTTP MCP endpoint path is `/mcp`.

## License

MIT
