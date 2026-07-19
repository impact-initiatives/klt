# =============================================================================
# Multi-stage Dockerfile for KLT (Kobo Loading Tool)
# Uses uv for fast dependency installation
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies with uv
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies (ref: https://docs.astral.sh/uv/guides/integration/docker/#non-editable-installs)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable --no-dev

# Copy the entire project
COPY . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Minimal production image
# -----------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 kltuser && \
    chown -R kltuser:kltuser /app

# Copy ONLY the virtual environment
# The project is installed in .venv/lib/python3.12/site-packages/klt
COPY --from=builder --chown=kltuser:kltuser /app/.venv /app/.venv

# Copy DLT config
COPY --chown=kltuser:kltuser .dlt/config.toml ./.dlt/config.toml

# Copy asset UID include/exclude filter (documented, reviewable allow/deny list)
COPY --chown=kltuser:kltuser asset_filters.toml ./asset_filters.toml

# Set Python path to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER kltuser

# Run the CLI tool (default command can be overridden at runtime)
ENTRYPOINT ["klt"]
CMD ["run"]
