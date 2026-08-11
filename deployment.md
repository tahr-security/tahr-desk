# Tahr Desk deployment and release

One image runs FastAPI, retry-safe prestart, and `python -m app.worker`.
PostgreSQL is the only companion image. FastAPI serves the compiled React app
and API on internal port 8000.

## Runtime contract

- App, prestart, and worker use UID/GID `10001:10001`.
- Every root filesystem is read-only; `/tmp` is bounded and `noexec`.
- All capabilities are dropped and `no-new-privileges` is enabled.
- `/app/data` is the only writable application volume; it contains `uploads/`
  and `exports/`.
- PostgreSQL is non-root, digest-pinned, and has no published port.
- App and worker share no provider credentials.
- Production deployments set `WEBHOOK_DELIVERY_ENABLED=false`.

Validate configuration before starting:

```bash
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml up -d --wait
```

Production must set `TAHR_DESK_IMAGE` to
`ghcr.io/tahr-security/tahr-desk@sha256:...`. Tags are not deployment evidence.
Back up the PostgreSQL volume and `/app/data`; restore both consistently.

## Publication

The publish workflow accepts only `vMAJOR.MINOR.PATCH`, verifies that tag,
backend, frontend, and changelog versions agree, calls complete CI, and pauses
at the protected `ghcr-production` environment. After approval it builds only
`linux/amd64`, publishes `MAJOR.MINOR.PATCH` and `sha-COMMIT` (never `latest`),
attaches maximum provenance and an SBOM, and retains Buildx metadata containing
the registry-returned digest.

It does not create the tag or a GitHub release.

## Release evidence and downstream onboarding

After separately approved publication, bind the source commit, template commit,
manifest hash, exact app and PostgreSQL digests, `linux/amd64` platform,
anonymous pull result, provenance, SBOM, licence review, secret scan,
vulnerability review, clean classification, and approvals into release
evidence. Run the manual smoke for seed data, reporter/staff workflows,
private-note isolation, uploads, exports, disabled webhooks, persistence,
prestart retry, UIDs, hardening, and cleanup.

Only then, and only after approval to consume the observed digest, add
`catalog/desk.yaml` beside existing applications. Add only
`desk:1.0.1:clean`; preserve every existing entry. Catalog merge,
synchronization, deployment, and any Cloudflare, Convex, Linode, GitHub, or
1Password mutation remain separately approved actions.
