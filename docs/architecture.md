# Architecture

## Components and boundaries

React is built once and served by FastAPI from the same origin. The frontend is
split into public and staff shells and feature routes; its only API contract is
the generated client. FastAPI routers validate transport details and delegate
to services:

- `auth`: JWTs, Argon2/bcrypt migration, user activity, and `auth_version`
- `desk`: case locking, authorization, lifecycle, messages, and audit events
- `content`: restricted CommonMark rendering and allowlist sanitization
- `storage`: JPEG/PNG validation, metadata removal, atomic writes, and paths
- `exports`: fixed ReportLab PDF and formula-safe CSV generation
- `webhooks`: endpoint validation, encryption, DNS pinning, signing, delivery
- `worker`: PostgreSQL leasing, retries, recovery, expiry, and cleanup

PostgreSQL stores UTC timestamps. The UI displays `America/Toronto`. Uploaded
bytes and generated exports live under `/app/data`, referenced by random storage
keys. No client filename becomes a path.

## Authorization

Reporters have no account. Reference plus normalized email authorizes a single
case and is accepted only in POST bodies. Reporter responses contain public
events/messages and protected photo metadata only.

Active agents can read all queues, claim an unassigned case, and mutate only
their assigned cases. They can assign only to themselves. Active superusers can
reassign/reopen and administer agents, site content, categories, and webhooks.
Password changes, resets, and deactivation increment `auth_version`, invalidating
existing eight-hour tokens.

## Lifecycle and concurrency

```text
submitted -> triaged -> in_progress -> resolved -> closed
                    \-> waiting_on_reporter -/
                    \-----------------------> closed
resolved -> in_progress
closed   -> in_progress (superuser only)
```

A reporter follow-up while waiting returns the case to `in_progress`.
Unresolved closure requires `duplicate`, `out_of_scope`, or `withdrawn`;
resolved closure uses `resolved`. Resolution and closed timestamps, assignment,
closure reason, and duplicate links are protected by service rules and database
constraints.

Case mutations lock the case row first, require a weak ETag version through
`If-Match`, and increment version once. Missing preconditions return 428; stale
writes return 412. Claim races yield one winner. Events and delivery rows are
part of the same transaction. Public submission uses UUID idempotency plus a
normalized payload/file hash.

## Jobs and integrations

The worker leases rows with `FOR UPDATE SKIP LOCKED`, expiring leases, bounded
batches, and sanitized error codes. PDFs exclude private notes and binary
attachments. CSV output is capped at 50,000 rows and neutralizes spreadsheet
formulas. Files expire after 24 hours; advisory-lock cleanup removes expired,
temporary, and unreferenced files.

Webhook delivery is opt-in. HTTPS endpoints reject credentials, query strings,
fragments, IP literals, non-443 production ports, and non-global DNS answers.
Delivery re-resolves then pins the approved address, disables redirects,
environment proxies, cookies, and decompression, uses 3/10-second timeouts,
bounds request/response sizes to 64 KiB, and signs timestamp, event ID, and exact
body with HMAC-SHA256. AES-GCM secrets are derived from `SECRET_KEY` using HKDF.

## API map

Public: site/services, multipart case creation, credential lookup, reporter
message, and protected attachment download under `/api/v1/public`.

Staff: dashboard, case list/detail/assignment/classification/transition/message,
attachments, and exports under `/api/v1/staff`.

Superuser: agents, site, services, and webhooks under `/api/v1/admin`. Login and
self-service remain `/api/v1/login/access-token` and `/api/v1/users/me`.

Handled failures use `{detail, code}`; validation retains FastAPI's 422 shape.
Credential-based public responses set `Cache-Control: no-store`.

## Future release seams

The upload processor, Markdown renderer, exporters, webhook transport, worker,
tracking policy, and staff policy layer are isolated seams. Any separately
authorized research modification must use a new immutable semantic version,
exact digest, classification evidence, and independent review.
