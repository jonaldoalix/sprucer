# Architecture

Sprucer splits into a **brain** (FastAPI + adapters) and a **web** UI. The CLI is a thin HTTP client of the brain.

## Adapters

| Concern | Interface | Implementations |
|---------|-----------|-----------------|
| Storage | `StorageAdapter` | **SQLite (default)**, Postgres, filesystem import (optional) |
| Auth | `AuthAdapter` | `dev` / `none` (local), `api_key`, `oidc` (generic) |
| LLM | `LlmAdapter` | OpenAI-compatible `/v1/chat/completions` |

Domain code never opens files or SQL directly. Generate always sends:

1. **System** — hard rules (ground in truth, neverClaim, keyboard punctuation, markdown structure)
2. **User** — JSON with `careerTruth`, `jobDescription`, application meta, artifact types, emphasis hint

## Default storage (SQLite)

Tables hold truth (JSON document), applications, JD text, generations, and fit interview sessions. Postgres uses the same schema via SQLAlchemy.

Career-fit interview (`/v1/fit/*`, UI `/fit`) is a separate multi-turn flow from JD materials generate; see [FIT_INTERVIEW.md](FIT_INTERVIEW.md).

## Filesystem vault (lab / migration only)

Some deployments historically used:

```text
career/
  current/career-truth.json
  applications/<id>/{meta.json,jd.txt,generations/*.md}
```

Sprucer can **import** that layout. It is not the default retention model. See [MIGRATION.md](MIGRATION.md).

## Auth

- `dev` — shared password session cookie; unsafe for internet exposure
- `none` — no gate (local scripts / trusted mesh only)
- `api_key` — `Authorization: Bearer <key>` for CLI/agents
- `oidc` — generic OIDC (Authentik, Auth0, Keycloak, …)

## Ports

| Service | Default |
|---------|---------|
| Brain | `8787` |
| Web | `3737` |
