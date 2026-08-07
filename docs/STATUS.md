# Local notes

## Still open before first public push

- [ ] Operator final brand sign-off (theme is now stronger; override via `theme.override.css`)
- [ ] Point a real IdP at OIDC and click through once (flow is implemented)
- [ ] URL ingest ATS edge cases (Workday/etc.) if you want lab parity
- [ ] Confirm LICENSE copyright line
- [ ] No lab hostnames / personal truth in history

## Done recently

- [x] Visual refresh + theming docs / override CSS
- [x] Richer knowledge-bank CRUD (experience, metrics, blurbs, stories, never-claim, headline)
- [x] OIDC authorization-code flow + `/v1/auth/config` + login SSO button
- [x] Postgres smoke path (`compose.example.yml` profile `postgres`)
- SQLite default storage + same models for Postgres URL
- Dev / none / api_key / oidc auth adapters
- OpenAI-compatible LLM + mock for tests
- FastAPI brain with truth / applications / ingest / generate / approve
- Filesystem vault importer
- Fixture synthetic truth + sample JD
- Web desk + CLI + CI
