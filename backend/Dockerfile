# Backend API image. Offline-job dependencies (geopandas, r5py, Java) are never
# installed here; they live in separate uv dependency groups.

# --- Stage 1: install the locked dependencies into a virtual environment -----
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
# Dependencies first: this layer is rebuilt only when the lock file changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Stage 2: the runtime, without uv or build files --------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY . .

RUN useradd --system --no-create-home app
USER app
EXPOSE 8000

# Migrations run first (a no-op when the database is current), so a new
# deployment never meets an older schema. Render and Cloud Run supply PORT;
# locally it falls back to 8000. Uvicorn's own access log is off because it
# records visitors' IP addresses; the app's request log (api/middleware.py)
# records path, status and timing without them.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
