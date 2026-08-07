# Deploy recipes for Sprucer

| File | Use |
|------|-----|
| [`../compose.yml`](../compose.yml) | Default local Docker: SQLite + brain + web |
| [`compose.postgres.yml`](compose.postgres.yml) | Postgres-backed brain (smoke / Dockge) |
| [`compose.oidc.yml`](compose.oidc.yml) | OIDC + Postgres + web (production-shaped) |
| [`compose.authentik.yml`](compose.authentik.yml) | Same as OIDC with Authentik-oriented comments |
| [`env.oidc.example`](env.oidc.example) | Env template for OIDC compose |
| [`env.authentik.example`](env.authentik.example) | Env template for Authentik-oriented compose |

All compose files are heavily commented — YAML `#` comments are intentional documentation.

## Dockge

1. Create a stack from this repo (or paste `compose.yml`).
2. Provide a `.env` with at least `SPRUCER_DEV_PASSWORD` and `SPRUCER_SESSION_SECRET`.
3. For OIDC stacks, use `--env-file` / Dockge env editor with `deploy/env.oidc.example` as the guide.
4. Put HTTPS in front before setting `SPRUCER_COOKIE_SECURE=1`.

## Safety reminders

- `SPRUCER_AUTH_MODE=dev` is for trusted networks only. Containers bind `0.0.0.0`, so local compose sets `SPRUCER_ALLOW_INSECURE_DEV=1` deliberately.
- Prefer `oidc` (or `api_key`) for anything reachable beyond your laptop.
- With auth enabled, each identity gets its own vault; `auth_mode=none` is one shared vault per database.
