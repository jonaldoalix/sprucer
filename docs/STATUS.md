# Local notes

## Still open before polished public v0

- [ ] Operator final brand sign-off (override via `theme.override.css`)
- [ ] Point a real IdP at OIDC and click through once (flow is implemented; compose samples in `deploy/`)
- [ ] Confirm LICENSE copyright line
- [ ] No lab hostnames / personal truth in history
- [ ] Rate limits on login / generate (not yet)
- [x] Per-identity vaults when auth is on; shared vault when `auth_mode=none`

## Done recently

- [x] Self-contained demo mode (`SPRUCER_DEMO=1`, `deploy/compose.demo.yml`): offline `DemoLlm` generator (no external LLM/cost), anonymous per-session ephemeral vaults with TTL sweep, auto-seeded sample vault, outbound URL ingest disabled
- [x] Demo start gate: first-run chooser between the offline generator (simulated) and bring-your-own-AI (prompts for ephemeral creds, Test connection via `/v1/llm/probe`, then unlocks real generation), plus a status strip to change setup
- [x] Dockge demo compose (`compose.demo.yaml`) for fsb-03 / sprucer.fullstackboston.com (Tailscale :8096)
- [x] Bring-your-own-key proxy (`SPRUCER_BYOK_ENABLED=1`): visitors supply their own OpenAI-compatible provider per request (key stays in the browser, SSRF-guarded https, optional host allowlist)
- [x] Richer JD ingest: Workday CXS JSON, HTML hero/`job-description` extraction, PDF/DOCX/DOC upload parsing, og:title/`<title>` field hints, URL-dedup (all behind the SSRF guard)
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
