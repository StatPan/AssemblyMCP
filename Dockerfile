# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    UV_PROJECT_ENVIRONMENT="/usr/local"

# Install system dependencies
# git is required for installing dependencies from git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy configuration files
COPY pyproject.toml uv.lock ./

# Install dependencies
# We use --system to install into the system python environment
RUN uv sync --frozen --no-dev

# Copy application code
COPY assemblymcp ./assemblymcp
COPY README.md ./

# Create directory for logs
RUN mkdir -p /tmp/assemblymcp && chmod 777 /tmp/assemblymcp

# Expose port (FastMCP default is 8000)
EXPOSE 8000

# Set transport to SSE
ENV MCP_TRANSPORT=sse

# Run the application
# We use 'uv run' to ensure we use the correct environment, though we installed to system
CMD ["uv", "run", "assemblymcp"]
