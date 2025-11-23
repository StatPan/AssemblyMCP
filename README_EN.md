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

*   **Member Information**
    *   `get_member_info(name)`: Get details about a National Assembly member (party, constituency, etc.).

*   **Advanced Tools**
    *   `get_assembly_info()`: Check server status and available API info.
    *   `list_api_services()`: Search for all available API services.
    *   `call_api_raw()`: (Advanced) Call API services directly with custom parameters.

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

## License

MIT
