# AssemblyMCP

MCP (Model Context Protocol) server for Korean National Assembly Open API

## Features

- FastMCP-based server implementation
- Integration with Korean National Assembly Open API
- Type-safe API interactions

## Development

### Requirements

- Python 3.12+
- uv package manager

### Setup

```bash
# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### Code Quality

- **ruff**: Linting and formatting
- **pytest**: Testing framework
- **pre-commit**: Automated code quality checks

### Running

```bash
uv run python main.py
```

## License

MIT
