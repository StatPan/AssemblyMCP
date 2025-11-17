# Development Conventions

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
- ❌ No "Generated with Claude Code" or similar
- ❌ No "Co-Authored-By: Claude" or similar
- ✅ Keep commits professional and focused on the changes

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

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

## Code Style

- Follow PEP 8
- Use type hints for function signatures
- Write docstrings for public functions and classes
- Keep functions focused and small
- Prefer explicit over implicit

## Testing

- Write tests for new features
- Maintain test coverage
- Use meaningful test names
- Follow AAA pattern (Arrange, Act, Assert)
