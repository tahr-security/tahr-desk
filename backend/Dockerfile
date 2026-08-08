# syntax=docker/dockerfile:1.7

FROM oven/bun:1.3.12-alpine@sha256:26d8996560ca94eab9ce48afc0c7443825553c9a851f40ae574d47d20906826d AS frontend-build

WORKDIR /src

COPY package.json bun.lock ./
COPY frontend/package.json frontend/package.json
RUN bun install --frozen-lockfile

COPY frontend frontend
WORKDIR /src/frontend

ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN bun run build


FROM ghcr.io/astral-sh/uv:0.11.18@sha256:78bc42400d77b0678ba95765305c826652ed5431f399257271dda681d0318f03 AS uv


FROM python:3.14.3-slim-bookworm@sha256:f21c0d5a44c56805654c15abccc1b2fd576c8d93aca0a3f74b4aba2dc92510e2 AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV HOME=/tmp \
    PATH=/app/.venv/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    XDG_CACHE_HOME=/tmp/cache

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/alembic.ini backend/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package tahr-desk --no-install-package tahr-desk

COPY backend/app backend/app
COPY backend/scripts backend/scripts
COPY --from=frontend-build /src/backend/app/frontend backend/app/frontend

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package tahr-desk \
    && groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --home-dir /tmp --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/uploads /app/data/exports \
    && chown -R "${APP_UID}:${APP_GID}" /app

WORKDIR /app/backend

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/utils/health-check/', timeout=3).read()"]

CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
