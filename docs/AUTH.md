# Authentication

Sprucer auth is pluggable via `SPRUCER_AUTH_MODE`.

| Mode | Use |
|------|-----|
| `dev` | Shared password cookie (local only — do not expose to the internet) |
| `none` | No gate (trusted mesh / scripts) |
| `api_key` | Bearer API keys for CLI/agents |
| `oidc` | Generic OpenID Connect authorization code flow |

Always set a unique `SPRUCER_SESSION_SECRET`. Binding `0.0.0.0` with `dev`/`none` requires `SPRUCER_ALLOW_INSECURE_DEV=1` (Docker local stacks set this on purpose). Behind HTTPS set `SPRUCER_COOKIE_SECURE=1`.

See [deploy/](../deploy/README.md) for OIDC / Authentik compose samples and [SECURITY.md](../SECURITY.md).

## OIDC (SSO)

Works with any standards-compliant IdP (Authentik, Auth0, Keycloak, Okta, …).

1. Create an OIDC application at your IdP.
2. Set redirect URI to your Sprucer callback, typically:
   `http://localhost:3737/v1/auth/oidc/callback` (web proxies `/v1` to the brain).
3. Configure env:

```bash
SPRUCER_AUTH_MODE=oidc
SPRUCER_SESSION_SECRET=long-random-value
SPRUCER_OIDC_ISSUER=https://auth.example.com/application/o/sprucer/
SPRUCER_OIDC_CLIENT_ID=...
SPRUCER_OIDC_CLIENT_SECRET=...
SPRUCER_OIDC_REDIRECT_URI=http://localhost:3737/v1/auth/oidc/callback
SPRUCER_OIDC_POST_LOGIN_REDIRECT=http://localhost:3737/applications
SPRUCER_API_KEYS=optional-machine-key
```

4. Open `/login` and use **Continue with SSO**.
5. **Logout** clears the Sprucer session cookie only (`POST /v1/auth/logout`). It does not end the IdP SSO session — that stays with Authentik/Auth0/etc. until their own logout.

Machine clients can still send `Authorization: Bearer <api-key>` when `SPRUCER_API_KEYS` is set.

**Tenancy:**

- `SPRUCER_AUTH_MODE=none` → one shared vault for the deploy (`owner_subject=shared`).
- Any other auth mode → truth and applications are scoped to the authenticated identity (`AuthContext.subject`).
  - `dev` → subject `dev` (everyone with the shared password shares one vault)
  - `oidc` → IdP `sub`
  - `api_key` → `api-key:<sha256-prefix>` (each key is its own vault)

Filesystem import / CLI seed into the shared vault by default. After enabling OIDC or API keys, re-import with the intended owner or migrate rows’ `owner_subject`.

