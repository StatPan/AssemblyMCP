## syntax=docker/dockerfile:1
# Build stage: create a locked virtualenv with uv (keeps git out of runtime)
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENV=/opt/venv

# git is only needed to pull the assembly-api-client dependency
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY assemblymcp ./assemblymcp

# Create the virtualenv and install production deps (including our package)
# uv writes to .venv by default; move it to a fixed path for the runtime image.
RUN uv sync --frozen --no-dev \
    && mv .venv /opt/venv \
    && rm -rf /root/.cache

# Runtime stage: minimal image with prebuilt venv and non-root user
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    MCP_PATH=/mcp

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /home/appuser/app

# Copy only what is needed to run
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/assemblymcp ./assemblymcp
COPY --from=builder /app/README.md ./README.md

USER appuser

# Expose port (Cloud Run default is 8080)
EXPOSE 8080

# Directly run the installed console script (uv not needed at runtime)
CMD ["python", "-m", "assemblymcp.server"]
