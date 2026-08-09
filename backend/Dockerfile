# syntax=docker/dockerfile:1.7

FROM oven/bun:1.3.14-alpine@sha256:5acc90a93e91ff07bf72aa90a7c9f0fa189765aec90b47bdbf2152d2196383c0 AS frontend-build

WORKDIR /src

COPY package.json bun.lock ./
COPY frontend/package.json frontend/package.json
RUN bun install --frozen-lockfile

COPY frontend frontend
WORKDIR /src/frontend

ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN bun run build


FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv


FROM python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52 AS backend-build

ENV UV_CACHE_DIR=/tmp/uv-cache \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/alembic.ini backend/
COPY backend/app backend/app
COPY backend/scripts backend/scripts
COPY --from=frontend-build /src/backend/app/frontend backend/app/frontend

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package tahr-desk


FROM python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52 AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV HOME=/tmp \
    PATH=/app/.venv/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/cache

WORKDIR /app

COPY --from=backend-build /app/.venv /app/.venv
COPY --from=backend-build /app/backend /app/backend

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --home-dir /tmp --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/uploads /app/data/exports \
    && chown -R "${APP_UID}:${APP_GID}" /app/data

WORKDIR /app/backend

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/utils/health-check/', timeout=3).read()"]

CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
