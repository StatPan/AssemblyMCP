# AssemblyMCP

MCP (Model Context Protocol) server for the Korean National Assembly Open API.
It enables AI agents like Claude to search, retrieve, and analyze legislative data, meeting records, and member information from the Korean National Assembly in real-time.

[한국어 설명 (Korean README)](README.md)

---

## Features

This server provides the following tools:

*   **Bill Search & Retrieval**
    *   `search_bills(keyword)`: Search for bills by keyword (e.g., "AI", "Budget").
    *   `get_recent_bills()`: Get a list of recently proposed bills.
    *   `get_bill_details(bill_id)`: Get detailed information (summary, reason for proposal) of a specific bill.
    *   `get_bill_info(...)`: Advanced search with filters like bill ID, proposer, date, etc.

*   **Meeting Records & Committees**
    *   `get_meeting_records(bill_id)`: Get committee meeting records related to a specific bill.
    *   `search_meetings(...)`: Search meeting records by date, committee name, etc.
    *   `get_committee_list()`: Get a list of National Assembly committees.
    *   `get_committee_members(...)`: Get the roster (member list) of a committee.

*   **Member Information**
    *   `get_member_info(name)`: Get details about a National Assembly member (party, constituency, etc.).

*   **Advanced Tools**
    *   `get_assembly_info()`: Check server status and available API info.
    *   `list_api_services()`: Search for all available API services.
    *   `call_api_raw()`: (Advanced) Call API services directly with custom parameters.

## LLM Usage Guide (Important)

- The server can reach **~270 National Assembly OpenAPI endpoints**. If a high-level tool is missing, do NOT answer “not supported.”
- Default pattern: `list_api_services(keyword)` → `get_api_spec(service_id)` → `call_api_raw(service_id, params)`. This lets you fetch any dataset.
- Search with broad keywords (Korean/English, spacing variants). Use `get_api_spec` to confirm required params, then call via `call_api_raw`.
- Example: “committee members” → search `list_api_services("위원 명단" or "committee member")` → inspect with `get_api_spec` → fetch with `call_api_raw` → enrich individuals via `get_member_info`.
- When replying: if a high-level tool is absent, propose this workflow or directly chain the calls to produce the answer.
- Shortcut: committee rosters are available directly via `get_committee_members`, then enrich individuals via `get_member_info`.

---

## Quick Start

This project is managed with `uv` and can be run directly using `uvx` without manual installation.

### 1. Get API Key
Obtain an API key from the [Public Data Portal (data.go.kr)](https://www.data.go.kr/). Look for APIs provided by the National Assembly Secretariat (국회사무처).

### 2. Claude Desktop Configuration

To use this MCP server with the Claude Desktop app, you need to configure it.

1.  Open the configuration file:
    *   **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
    *   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2.  Add the following configuration. (Replace `your_api_key_here` with your actual API key)

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

3.  Restart Claude Desktop. You should see the 🔌 icon indicating the AssemblyMCP tools are active.

### 3. Running Directly (Testing)

You can run the server directly in your terminal to verify it starts correctly.

```bash
# Set API Key (Linux/macOS)
export ASSEMBLY_API_KEY="your_api_key_here"

# Run Server
# Fetches the latest code from GitHub and runs it.
uvx git+https://github.com/StatPan/AssemblyMCP
```

---

To contribute or run locally for development:

### Requirements
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup & Run

```bash
# 1. Clone repository
git clone https://github.com/StatPan/AssemblyMCP.git
cd AssemblyMCP

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env and add your ASSEMBLY_API_KEY

# 4. Run development server
uv run assemblymcp
```

### Code Quality
```bash
# Lint and Format
uv run ruff check .
uv run ruff format .

# Run Tests
uv run pytest
```

## Configuration & Hosting

AssemblyMCP adopts a **"Battery-Included"** architecture, allowing you to control operational features like logging and caching via environment variables without modifying the code.

### Environment Variables

| Variable | Description | Default | Example |
| :--- | :--- | :--- | :--- |
| `ASSEMBLY_API_KEY` | **[Required]** API Key | - | `1234abcd...` |
| `ASSEMBLY_LOG_LEVEL` | Logging Level | `INFO` | `DEBUG` |
| `ASSEMBLY_LOG_JSON` | Enable JSON Logging (for Cloud Run) | `False` | `True` |
| `ASSEMBLY_ENABLE_CACHING` | Enable In-Memory Caching | `False` | `True` |
| `ASSEMBLY_CACHE_TTL_SECONDS` | Cache TTL (seconds) | `300` (5 min) | `600` |
| `ASSEMBLY_CACHE_MAX_SIZE` | Max Cache Items | `100` | `500` |

### Production Mode

For serverless environments like Cloud Run or AWS Lambda, we recommend the following settings:

```bash
# Enable JSON logging for structured logs
export ASSEMBLY_LOG_JSON=true

# Enable caching to reduce API calls and improve speed
export ASSEMBLY_ENABLE_CACHING=true
```

## Deployment

This server can be easily deployed to cloud platforms like Google Cloud Run, Railway, and Fly.io using Docker.

### Docker Deployment

1. A **Dockerfile** is included, so you can build immediately.
2. Set the required environment variables (e.g., `ASSEMBLY_API_KEY`) during deployment.
3. The server runs in `Streamable HTTP` mode on port `8000` by default.

### Google Cloud Run Example

```bash
gcloud run deploy assembly-mcp \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars ASSEMBLY_API_KEY="your_key",ASSEMBLY_LOG_JSON="true",ASSEMBLY_ENABLE_CACHING="true"
```

### Key Changes

- **Streamable HTTP Transport**: Uses the latest MCP standard.
- **Endpoint**: The MCP server runs at `/mcp`.

## License

MIT
