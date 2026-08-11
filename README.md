# Tahr Desk

Tahr Desk is a civic service-request intake and case-management application for
small municipalities. Pinehaven residents can browse service standards, submit
an issue with optional photos, and privately follow its public timeline using an
unguessable reference plus their email address. Staff triage, claim, classify,
message, resolve, close, export, and audit cases from an authenticated workspace.

Version `1.0.1:clean` is a focused single-tenant product. It has no payment,
mapping, reporter accounts, email/SMS delivery, paid service, deliberate
vulnerability, hidden credential, or unsafe default.

## Stack

- FastAPI, SQLModel, PostgreSQL, and Alembic
- React 19, TypeScript, TanStack Router/Query, Tailwind, and Radix UI
- React Hook Form, Zod, and an OpenAPI-generated TypeScript client
- uv, Bun, Pytest, and Playwright
- A hardened same-image app, prestart, and PostgreSQL-backed worker runtime

The code is based on Full-Stack FastAPI Template commit
`d506ea4883c0f7bfcf5280921cfc407c46808711`.

## Local Compose start

Requires Docker with Compose v2. Copy `.env.example` to `.env`, replace the
three required secret placeholders with independent random values, and use the
local image name:

```bash
docker build -f backend/Dockerfile -t tahr-desk:local .
docker compose -f compose.production.yml up -d --wait
```

Open <http://localhost:8000>. The API schema is at
<http://localhost:8000/api/v1/openapi.json> and health is at
<http://localhost:8000/api/v1/utils/health-check/>. PostgreSQL is not published.

Prestart is retry-safe: it waits for PostgreSQL, migrates, creates the configured
first superuser only when absent, fills missing seed content, and creates demo
cases only when the case table is empty. It never rotates an existing password.

## Product routes

Public pages: `/`, `/services`, `/services/:slug`, `/report`, `/track`, and
`/login`. Staff pages: `/admin`, `/admin/cases`, `/admin/exports`,
`/admin/account`, plus superuser agent and settings pages.

The administrator bootstrap protocol remains:

- `POST /api/v1/login/access-token`
- `GET /api/v1/users/me`
- JWT bearer authentication with active-user and active-superuser checks
- `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD`

Tracking credentials are accepted only in POST bodies. They are never placed in
routes, query strings, analytics, or application logs.

## Documentation

- [Development](development.md)
- [Architecture](docs/architecture.md)
- [Environment](docs/environment.md)
- [Deployment and release](deployment.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Release boundary

No workflow creates a tag or GitHub release. Pushing source or tags, approving
the protected publication environment, publishing an image, changing GHCR
visibility, using a registry-observed digest in an external deployment catalog,
synchronizing that catalog, and deploying are separate explicit operator approvals.

No deployment catalog file is included before a public `linux/amd64` image exists
and its exact registry-observed digest has been independently approved.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
