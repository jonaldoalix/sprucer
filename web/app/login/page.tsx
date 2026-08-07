"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

type AuthConfig = {
  mode?: string;
  dev_login?: boolean;
  oidc_login?: boolean;
  oidc_start?: string;
  issuer?: string;
};

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    apiFetch("/v1/auth/config")
      .then((json) => setConfig(json as AuthConfig))
      .catch((err) => setError(err instanceof Error ? err.message : "Config failed"));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiFetch("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      router.push("/applications");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="hero compact">
        <div className="eyebrow">Sign in</div>
        <h1>Your desk, your identity provider.</h1>
        <p>
          Local installs use a shared password. Production installs can switch to generic OIDC
          (Authentik, Auth0, Keycloak, and others) without locking you to one vendor.
        </p>
      </section>
      <div className="panel" style={{ maxWidth: 460 }}>
        {config?.oidc_login ? (
          <div className="actions" style={{ marginBottom: "1rem" }}>
            <a className="btn" href={config.oidc_start || "/v1/auth/oidc/start"}>
              Continue with SSO
            </a>
          </div>
        ) : null}
        {config?.issuer ? <p className="muted">Issuer: {config.issuer}</p> : null}
        {config?.dev_login !== false ? (
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="password">Dev password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            {error ? <p className="error">{error}</p> : null}
            <div className="actions">
              <button className="btn" type="submit" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </div>
            <p className="muted" style={{ marginTop: "0.85rem" }}>
              Dev auth is for local use only. Set <code>SPRUCER_AUTH_MODE=oidc</code> and the{" "}
              <code>SPRUCER_OIDC_*</code> vars for SSO.
            </p>
          </form>
        ) : error ? (
          <p className="error">{error}</p>
        ) : null}
      </div>
    </>
  );
}
