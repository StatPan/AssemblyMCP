# AssemblyMCP

MCP (Model Context Protocol) server for Korean National Assembly Open API. (Currently in **BETA** stage.)

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for a high-level overview of the design.

## Features

- FastMCP-based server implementation
- Integration with Korean National Assembly Open API
- **Dynamic API endpoint resolution** via Excel spec parsing
- Type-safe API interactions
- Automatic spec caching for performance
- Environment-based configuration

## Quick Start

### 1. Get API Key

Get your API key from [공공데이터포털](https://www.data.go.kr/)

### 2. Run with uvx

```bash
# Set API key as environment variable
export ASSEMBLY_API_KEY="your_api_key_here"

# Run MCP server
uvx assemblymcp
```

### 3. Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "assembly": {
      "command": "uvx",
      "args": ["assemblymcp"],
      "env": {
        "ASSEMBLY_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Development

### Requirements

- Python 3.12+
- uv package manager

### Setup

```bash
# Clone repository
git clone https://github.com/StatPan/AssemblyMCP.git
cd AssemblyMCP

# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env and add your API key
```

### Running in Development

```bash
# Using uv
uv run assemblymcp

# Or with environment variable
ASSEMBLY_API_KEY="your_key" uv run assemblymcp
```

### Code Quality

- **ruff**: Linting and formatting
- **pytest**: Testing framework
- **pre-commit**: Automated code quality checks

See [CONVENTIONS.md](docs/CONVENTIONS.md) for detailed development guidelines.

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - High-level architecture and design decisions
- [SPEC_PARSER.md](docs/SPEC_PARSER.md) - Excel spec parser documentation
- [CONVENTIONS.md](docs/CONVENTIONS.md) - Development conventions and guidelines

## Contributing

We welcome contributions! Please see [CONVENTIONS.md](docs/CONVENTIONS.md) for coding standards, setup instructions, and the process for submitting pull requests.

## Contributing

We welcome contributions! Please see [CONVENTIONS.md](docs/CONVENTIONS.md) for coding standards, setup instructions, and the process for submitting pull requests.

## License

MIT
