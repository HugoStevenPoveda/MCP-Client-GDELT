# Multi-stage Dockerfile for Cliente MCP using uv

# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv using pip (no network dependencies needed)
RUN pip install --no-cache-dir uv

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync (creates .venv with exact lockfile versions)
RUN uv sync --frozen --no-dev

# Copy source code
COPY src ./src

# ============================================
# Stage 2: Runtime - Minimal production image
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/src ./src

# Expose port for Gradio interface
EXPOSE 7860

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"

# Run the Gradio app
CMD ["python", "-m", "cliente_mcp.app"]
