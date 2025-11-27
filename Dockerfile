# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
# git is required for installing dependencies from git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /home/appuser/app
RUN mkdir -p /home/appuser/app && chown appuser:appuser /home/appuser/app

# Copy configuration files and set ownership
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
COPY --chown=appuser:appuser README.md ./
COPY --chown=appuser:appuser assemblymcp ./assemblymcp

# Switch to non-root user
USER appuser

# Install dependencies
# We use --frozen to ensure we use the lockfile
RUN uv sync --frozen --no-dev

# Create directory for logs with correct permissions
RUN mkdir -p /tmp/assemblymcp && chmod 755 /tmp/assemblymcp

# Expose port (FastMCP default is 8000)
EXPOSE 8000

# Set transport to Streamable HTTP (the new MCP standard)
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp

# Run the application
# We use 'uv run' to ensure we use the correct environment
CMD ["uv", "run", "assemblymcp"]
