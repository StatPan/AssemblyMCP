# Release Guide

This project follows [Semantic Versioning](https://semver.org/) (SemVer) and maintains a [CHANGELOG.md](../CHANGELOG.md) to track changes.

## Versioning Strategy

We use the format `MAJOR.MINOR.PATCH`:

* **MAJOR**: Incompatible API changes.
* **MINOR**: Backward-compatible functionality (new features).
* **PATCH**: Backward-compatible bug fixes.

## Release Process

Follow these steps to cut a new release:

### 1. Update Version Numbers

You must update the version string in **two** locations:

1.  `pyproject.toml`: Update the `version` field.
2.  `assemblymcp/__init__.py`: Update the `__version__` variable.

### 2. Update Changelog

1.  Open `CHANGELOG.md`.
2.  Change the `[Unreleased]` header to the new version number and today's date (e.g., `[0.2.0] - 2024-03-20`).
3.  Create a new empty `[Unreleased]` section at the top for future changes.

### 3. Commit and Tag

Create a release commit and tag it in git:

```bash
# Stage the version files
git add pyproject.toml assemblymcp/__init__.py CHANGELOG.md

# Commit with a standard message
git commit -m "chore: release v0.1.0"

# Create a git tag
git tag -a v0.1.0 -m "Release v0.1.0"

# Push to GitHub
git push origin main
git push origin v0.1.0
```

### 4. Build and Publish (Optional)

If you are publishing to PyPI, use `uv` or `build`:

```bash
# Build the package
uv build

# Publish (requires PyPI credentials)
uv publish
```
