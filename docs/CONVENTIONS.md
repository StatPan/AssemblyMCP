# Development Conventions

## Dependency Management

This project uses **uv** for all dependency management.

### Adding Dependencies

**ALWAYS use `uv add` command, NEVER manually edit `pyproject.toml`**

```bash
# Add production dependency
uv add httpx

# Add development dependency
uv add --dev pytest-asyncio

# Add multiple dependencies
uv add httpx beautifulsoup4 lxml
```

### Updating Dependencies

```bash
# Update all dependencies
uv sync --upgrade

# Update specific package
uv add httpx --upgrade
```

### Installing Project

```bash
# Install all dependencies (production + dev)
uv sync

# Install production dependencies only
uv sync --no-dev
```

### Important

**DO NOT manually edit dependencies in `pyproject.toml`**
- Use `uv add` for adding dependencies
- Use `uv remove` for removing dependencies
- Let uv manage version constraints automatically

## Code Quality Tools

### Ruff

Fast Python linter and formatter (replaces Flake8, Black, isort)

**Configuration**: `pyproject.toml`
- Line length: 100 characters
- Target: Python 3.12+
- Enabled rules: pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, flake8-bugbear, flake8-comprehensions, flake8-simplify

**Usage**:
```bash
# Check code
uv run ruff check .

# Format code
uv run ruff format .

# Fix issues automatically
uv run ruff check --fix .
```

### Pytest

Testing framework

**Configuration**: `pyproject.toml`
- Test directory: `tests/`
- Test file pattern: `test_*.py`

**Usage**:
```bash
uv run pytest
```

### Pre-commit

Automated code quality checks before commits

**Hooks**:
- trailing-whitespace
- end-of-file-fixer
- check-yaml, check-json, check-toml
- check-added-large-files
- ruff (lint + format)

**Usage**:
```bash
# Run manually
uv run pre-commit run --all-files
```

## Branch Naming

### Format

```
<type>/<issue-number>-<description>
```

### Types

Same as commit types (feat, fix, docs, style, refactor, test, chore).

### Guidelines

- Always include the issue number
- Use lowercase and hyphens for description
- Keep it short and descriptive

### Examples

- `feat/13-discovery-tools`
- `fix/42-login-error`
- `docs/10-update-readme`

## Git Commit Messages

### Format

```
<type>: <subject>

<body>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Build process, dependencies, tooling

### Guidelines

- Use present tense ("add feature" not "added feature")
- Use imperative mood ("move cursor to..." not "moves cursor to...")
- First line should be 50 characters or less
- Reference issues when applicable

### Important

**DO NOT include AI assistant attribution in commit messages**
- No "Generated with Claude Code" or similar
- No "Co-Authored-By: Claude" or similar
- Keep commits professional and focused on the changes

**DO NOT use emojis in commit messages, code, or documentation**
- Keep all text professional and clean
- Use plain text markers instead (e.g., [X], [OK], WARNING:, NOTE:)

### Examples

Good:
```
feat: add bill search API endpoint

Implement search functionality for National Assembly bills
with filtering by date, status, and keyword.
```

Bad:
```
Added some stuff

Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

## Code Style

- Follow PEP 8
- Use type hints for function signatures
- Write docstrings for public functions and classes
- Keep functions focused and small
- Prefer explicit over implicit
- **NO emojis** in code, comments, docstrings, or output messages

## Testing

- Write tests for new features
- Maintain test coverage
- Use meaningful test names
- Follow AAA pattern (Arrange, Act, Assert)
