# Environment reference

| Variable | Required | Sensitive | Default / purpose |
| --- | --- | --- | --- |
| `ENVIRONMENT` | yes | no | `local`, `staging`, or `production`; non-local rejects known placeholders. |
| `PROJECT_NAME` | yes | no | OpenAPI title; Compose defaults to `Tahr Desk`. |
| `SECRET_KEY` | yes | yes | Independent high-entropy JWT and webhook-key root. |
| `FIRST_SUPERUSER` | yes | no | Bootstrap email; Compose defaults to `demo-admin@tahr.ca`. |
| `FIRST_SUPERUSER_PASSWORD` | yes | yes | Used only when that user is absent; never rotates it. |
| `POSTGRES_SERVER` | yes | no | PostgreSQL host; `db` in Compose. |
| `POSTGRES_PORT` | no | no | Defaults to `5432`. |
| `POSTGRES_DB` | yes | no | Defaults to `tahr_desk` in Compose. |
| `POSTGRES_USER` | yes | no | Defaults to `tahr_desk` in Compose. |
| `POSTGRES_PASSWORD` | yes | yes | PostgreSQL role password. |
| `FRONTEND_HOST` | yes | no | Canonical browser origin. |
| `BACKEND_CORS_ORIGINS` | no | no | Comma-separated or JSON-list allowed origins. |
| `DATA_ROOT` | no | no | `/app/data` in containers. |
| `WEBHOOK_DELIVERY_ENABLED` | no | no | `false`; production deployments should keep it false. |
| `WEBHOOK_ALLOW_HTTP` | no | no | `false`; only a local webhook harness may opt in. |
| `WORKER_POLL_SECONDS` | no | no | Worker idle poll interval; defaults to `1`. |
| `TAHR_DESK_IMAGE` | yes | no | Local tag for development; exact `@sha256:` for release/deployment. |
| `APP_BIND_ADDRESS` | no | no | Host bind; defaults to `127.0.0.1`. |
| `APP_PORT` | no | no | Host port; defaults to `8000`. |
| `POSTGRES_VOLUME` | no | no | PostgreSQL named volume override. |
| `APP_DATA_VOLUME` | no | no | Upload/export named volume override. |
| `TAHR_DESK_NETWORK` | no | no | Compose network override. |

Never place secrets in source, image layers, URLs, logs, examples, screenshots,
or release evidence. Supply them through an approved runtime secret mechanism.
