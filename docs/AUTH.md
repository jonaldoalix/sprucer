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

Machine clients can still send `Authorization: Bearer <api-key>` when `SPRUCER_API_KEYS` is set.

**Note:** OIDC subjects are not isolated into separate vaults yet — one database is one knowledge bank.
