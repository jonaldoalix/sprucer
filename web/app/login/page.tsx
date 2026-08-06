"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
      <section className="hero">
        <h1>Local login</h1>
        <p>
          Dev auth uses a shared password from <code>SPRUCER_DEV_PASSWORD</code>. Do not
          expose this mode to the public internet. OIDC is available for real deployments.
        </p>
      </section>
      <div className="panel" style={{ maxWidth: 420 }}>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="password">Password</label>
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
        </form>
      </div>
    </>
  );
}
