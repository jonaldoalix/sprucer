# Sprucer

Truth-first application materials. Keep a knowledge bank of facts you will defend, ingest a job description, generate drafts via any OpenAI-compatible chat endpoint, track applications, and approve documents before you send them.

Sprucer does **not** invent employers, dates, degrees, or metrics. Generations save as drafts until you explicitly approve them.

> Alpha software. Safe for local / trusted-network use. Read [SECURITY.md](SECURITY.md) before exposing a port.

## Features

- **Knowledge bank** — structured career truth (experience, projects, metrics, blurbs, signature stories, never-claim) plus profile and voice prefs
- **JD ingest** — paste, URL fetch (SSRF-guarded), or upload
- **Generate** — cover letter, resume sections, email, interview prep, LinkedIn, custom types — grounded in your vault
- **Application tracker** — per-job status, notes, generation history
- **Document review** — draft → approve preview flow
- **Themes** — light / neutral / dark (topbar select)

## Quick start (Docker)

```bash
cp .env.example .env
# set SPRUCER_DEV_PASSWORD and SPRUCER_SESSION_SECRET to unique values
docker compose up --build
```

Open http://127.0.0.1:3737 — log in with `SPRUCER_DEV_PASSWORD`.

More recipes (Postgres, OIDC, Authentik-oriented) live under [`deploy/`](deploy/README.md). Compose files include inline `#` comments.

## Quick start (local Python + Next)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# API (SQLite default) — binds SPRUCER_HOST from .env (default 127.0.0.1)
sprucer-brain

# In another shell: web UI
cd web && npm install && npm run dev
```

Open http://localhost:3737. API defaults to http://127.0.0.1:8787 (the web UI proxies `/v1`).

Optional helper that starts mock LLM + brain + web if they are not already running:

```bash
./scripts/ensure-dev-stack.sh
```

## Configuration

| Variable | Purpose |
|----------|---------|
| `SPRUCER_DATABASE_URL` | Default `sqlite:///./data/sprucer.db`. Postgres: `postgresql+psycopg://user:pass@host/db` |
| `SPRUCER_AUTH_MODE` | `dev` (local only) \| `none` \| `oidc` \| `api_key` |
| `SPRUCER_DEV_PASSWORD` | Shared password when `auth_mode=dev` |
| `SPRUCER_SESSION_SECRET` | HMAC secret for session cookies — **change this** |
| `SPRUCER_ALLOW_INSECURE_DEV` | `1` to allow `dev`/`none` while binding `0.0.0.0` (lab/Docker only) |
| `SPRUCER_COOKIE_SECURE` | `1` to set the Secure flag (HTTPS) |
| `SPRUCER_DOCS_ENABLED` | `0` to disable `/docs` and `/redoc` |
| `SPRUCER_LLM_URL` | OpenAI-compatible base (e.g. `http://127.0.0.1:4000/v1`) |
| `SPRUCER_LLM_API_KEY` | Bearer token for the LLM endpoint |
| `SPRUCER_LLM_MODEL` | Model id (e.g. `qwen-coder`, `gpt-4o-mini`) |
| `SPRUCER_OIDC_*` | Issuer / client / secret / redirect when `auth_mode=oidc` |
| `SPRUCER_CORS_ORIGINS` | Comma-separated browser origins |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/AUTH.md](docs/AUTH.md), [docs/THEMING.md](docs/THEMING.md), [docs/TRUTH_SCHEMA.md](docs/TRUTH_SCHEMA.md), [deploy/README.md](deploy/README.md), and [SECURITY.md](SECURITY.md).

## Hard rules (product)

- Ground generations only in career truth + the job description
- Respect `neverClaim`
- Prefer keyboard punctuation in operator-facing copy and generated drafts
- Confirm before delete or approve

## Development

```bash
pytest -q --cov=sprucer --cov-fail-under=100
ruff check src tests
```

CI also runs Semgrep (`p/python`, `p/owasp-top-ten`) and a Next.js production build.

## Repo layout

```text
src/sprucer/          # brain: adapters, domain, FastAPI
web/                  # Next.js UI
deploy/               # Commented compose/env samples (OIDC, Authentik, Postgres)
fixtures/             # synthetic truth + sample JD (no real PII)
docs/
tests/
compose.yml           # default local Docker stack
```

## Status

Public alpha toward v0. Local Docker and lab installs are the supported paths. Do not commit operator truth, `.env`, or private hostnames.

## License

MIT — see [LICENSE](LICENSE).
