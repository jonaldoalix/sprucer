# Local notes

## Still open before polished public v0

- [ ] Operator final brand sign-off (override via `theme.override.css`)
- [ ] Point a real IdP at OIDC and click through once (flow is implemented; compose samples in `deploy/`)
- [ ] URL ingest ATS edge cases (Workday/etc.) if you want lab parity
- [ ] Confirm LICENSE copyright line
- [ ] No lab hostnames / personal truth in history
- [ ] Rate limits on login / generate (not yet)
- [ ] Multi-tenant vault isolation (explicitly out of scope for alpha)

## Done recently

- [x] Theme modes (light / lichen-slate neutral / dark) + compact select
- [x] SSRF guards on URL ingest + insecure-dev bind refusal
- [x] SECURITY.md, Semgrep CI, pytest coverage gate ≥80%
- [x] Docker `compose.yml` + commented `deploy/` recipes (Postgres, OIDC, Authentik-oriented)
- [x] Visual refresh + theming docs / override CSS
- [x] Richer knowledge-bank CRUD
- [x] OIDC authorization-code flow + `/v1/auth/config` + login SSO button
- [x] Postgres smoke path (`deploy/compose.postgres.yml`)
- SQLite default storage + same models for Postgres URL
- Dev / none / api_key / oidc auth adapters
- OpenAI-compatible LLM + mock for tests
- FastAPI brain with truth / applications / ingest / generate / approve
- Filesystem vault importer
- Fixture synthetic truth + sample JD
- Web desk + CLI + CI
