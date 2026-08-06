# Local notes (not for public release checklist yet)

## Still open before first public push

- [ ] Operator brand review of visual identity
- [ ] Full OIDC browser callback in web (brain already accepts `x-sprucer-oidc-sub` / API keys)
- [ ] Postgres live smoke test against a real server
- [ ] Richer knowledge-bank editors (experience/metrics/stories CRUD in UI)
- [ ] URL ingest ATS edge cases parity with lab (Workday CXS, etc.)
- [ ] Confirm LICENSE copyright line
- [ ] No lab hostnames / personal truth in history

## Done for local scaffold

- SQLite default storage + same models for Postgres URL
- Dev / none / api_key / oidc-stub auth adapters
- OpenAI-compatible LLM + mock for tests
- FastAPI brain with truth / applications / ingest / generate / approve
- Filesystem vault importer
- Fixture synthetic truth + sample JD
- Web: home, login, applications, knowledge
- CLI thin client + import-vault / load-fixture
- CI workflow (tests + web build)
