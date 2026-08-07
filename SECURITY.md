# Security Policy

## Supported versions

Sprucer is alpha (`0.1.x`). Security fixes land on `main`.

## Threat model (honest)

- **Intended:** single-operator career desk; drafts until you approve; local Docker or private network.
- **Not intended (yet):** multi-tenant SaaS, untrusted multi-user vaults, public anonymous generate APIs.
- OIDC authenticates a subject but **does not isolate data** — one database = one vault.

## Hardening already in place

- Auth modes: `dev` (local), `api_key`, `oidc`, `none`
- Refuses `dev`/`none` on non-loopback binds unless `SPRUCER_ALLOW_INSECURE_DEV=1`
- Session cookies: `HttpOnly`, `SameSite=Lax`, optional `Secure` via `SPRUCER_COOKIE_SECURE`
- JD URL ingest: http(s) only, blocks loopback/private/link-local/metadata, re-checks redirects
- Optional disable of `/docs` via `SPRUCER_DOCS_ENABLED=0`
- Dev Bearer auth accepts HMAC session tokens only (not the raw password)

## Reporting

Email security concerns to the maintainers via the GitHub security advisory flow on the public repo, or open a private report if available. Do not file public issues with exploit PoCs against live deployments.

## Operator checklist before exposure

1. Set unique `SPRUCER_SESSION_SECRET` and never keep example defaults
2. Use `SPRUCER_AUTH_MODE=oidc` (or `api_key`) — not `dev` — off your laptop
3. Terminate TLS; set `SPRUCER_COOKIE_SECURE=1`
4. Restrict `SPRUCER_CORS_ORIGINS`
5. Point `SPRUCER_LLM_*` at a trusted endpoint; treat job-description text as untrusted input to the model
6. Keep backups of the SQLite/Postgres volume; they contain career PII
