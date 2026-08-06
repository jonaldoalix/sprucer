# Sprucer

Truth-first application materials. Keep a knowledge bank of facts you will defend, ingest a job description, generate drafts via any OpenAI-compatible chat endpoint, track applications, and approve documents before you send them.

Sprucer does **not** invent employers, dates, degrees, or metrics. Generations save as drafts until you explicitly approve them.

## Features

- **Knowledge bank** — structured career truth (experience, projects, metrics, blurbs, signature stories, never-claim) plus profile and voice prefs
- **JD ingest** — paste, URL fetch, or upload
- **Generate** — cover letter, resume sections, email, custom types — grounded in your vault
- **Application tracker** — per-job status, notes, generation history
- **Document review** — draft → approve preview flow

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# API (SQLite default)
sprucer-brain

# In another shell: web UI
cd web && npm install && npm run dev
```

Open http://localhost:3737 — API defaults to http://127.0.0.1:8787.

Compose (API + web, SQLite volume):

```bash
docker compose -f compose.example.yml up --build
```

## Configuration

| Variable | Purpose |
|----------|---------|
| `SPRUCER_DATABASE_URL` | Default `sqlite:///./data/sprucer.db`. Postgres: `postgresql+psycopg://user:pass@host/db` |
| `SPRUCER_AUTH_MODE` | `dev` (default, local only) \| `none` \| `oidc` \| `api_key` |
| `SPRUCER_DEV_PASSWORD` | Shared password when `auth_mode=dev` |
| `SPRUCER_LLM_URL` | OpenAI-compatible base (e.g. `http://127.0.0.1:4000/v1`) |
| `SPRUCER_LLM_API_KEY` | Bearer token for the LLM endpoint |
| `SPRUCER_LLM_MODEL` | Model id (e.g. `qwen-coder`, `gpt-4o-mini`) |
| `SPRUCER_OIDC_*` | Issuer / client id / secret when `auth_mode=oidc` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/TRUTH_SCHEMA.md](docs/TRUTH_SCHEMA.md), and [docs/MIGRATION.md](docs/MIGRATION.md) (filesystem vault import).

## Hard rules (product)

- Ground generations only in career truth + the job description
- Respect `neverClaim`
- Prefer keyboard punctuation in operator-facing copy and generated drafts
- Confirm before delete or approve

## Repo layout

```text
src/sprucer/          # brain: adapters, domain, FastAPI
cli/                  # thin HTTP client
web/                  # Next.js UI (own design system)
fixtures/             # synthetic truth + sample JD (no real PII)
docs/
tests/
compose.example.yml
```

## Status

Local development toward a public v0. Not yet tagged for release. Do not push operator truth or lab hostnames into git.

## License

MIT — see [LICENSE](LICENSE).
