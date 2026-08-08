# Contributing to Tahr Desk

Keep changes focused, tested, accessible, and free of secrets. Discuss large
product, schema, authentication, storage, webhook, or deployment changes first.

Follow [development.md](development.md). API changes require regenerated
OpenAPI/client artifacts. Schema changes require an Alembic round trip.
User-facing changes require keyboard, responsive, Playwright, and axe coverage.
Before review, run the backend checks with 90% coverage, frontend lint/build,
generated-client drift check, and relevant container tests.

Preserve these invariants:

- Wardenn bootstrap routes, variables, JWT bearer auth, and active-superuser check
- case-first lock order, `If-Match`, atomic event creation, and retry idempotency
- private-note isolation and reference/email body-only tracking
- image re-encoding, random storage keys, and bounded uploads
- read-only roots, UID 10001, capability drop, and unexposed PostgreSQL
- no deliberate vulnerability, bypass, credential, unsafe default, or dormant mode

Never commit `.env`, credentials, database dumps, private uploads, generated
evidence containing secrets, or provider state. Publication and deployment are
maintainer operations requiring explicit approval.
