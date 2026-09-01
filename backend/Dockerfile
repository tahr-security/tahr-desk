# syntax=docker/dockerfile:1.7

FROM oven/bun:1.4.0-alpine@sha256:07235578f79ef8c6f97d94aee7938e76f5cdba5f21ae5dbfdd3d3d38058437eb AS frontend-build

WORKDIR /src

COPY package.json bun.lock ./
COPY frontend/package.json frontend/package.json
RUN bun install --frozen-lockfile

COPY frontend frontend
WORKDIR /src/frontend

ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN bun run build


FROM ghcr.io/astral-sh/uv:0.12.8@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a AS uv


FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS backend-build

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


FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS runtime

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
