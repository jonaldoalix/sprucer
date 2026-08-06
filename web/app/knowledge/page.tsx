"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Truth = {
  headline?: string;
  profile?: { name?: string; location?: string };
  metrics?: { id?: string; text?: string }[];
  blurbs?: { id?: string; label?: string; text?: string }[];
  neverClaim?: string[];
  experience?: { id?: string; org?: string; role?: string; dates?: string }[];
  signatureStories?: { id?: string; title?: string; body?: string }[];
};

export default function KnowledgePage() {
  const [truth, setTruth] = useState<Truth | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [blurb, setBlurb] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const json = await apiFetch("/v1/truth");
    setTruth(json.truth as Truth);
    setCounts((json.counts as Record<string, number>) || {});
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Load failed"));
  }, [load]);

  async function addBlurb(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiFetch("/v1/truth", {
        method: "PATCH",
        body: JSON.stringify({
          op: "add",
          section: "blurbs",
          item: { text: blurb, label: "Quick add" },
        }),
      });
      setBlurb("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeBlurb(id: string) {
    if (!window.confirm("Remove this blurb?")) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/v1/truth", {
        method: "PATCH",
        body: JSON.stringify({
          op: "remove",
          section: "blurbs",
          item_id: id,
          confirm: true,
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Knowledge bank</h1>
        <p>
          Facts you will defend. Generations are grounded only in this vault. Never-claim
          entries are hard stops.
        </p>
      </section>

      {error ? <p className="error">{error}</p> : null}

      <div className="panel">
        <h2>{truth?.profile?.name || "Profile"}</h2>
        <p className="muted">
          {truth?.headline || "No headline yet"}
          {truth?.profile?.location ? ` · ${truth.profile.location}` : ""}
        </p>
        <p className="muted">
          metrics {counts.metrics || 0} · blurbs {counts.blurbs || 0} · stories{" "}
          {counts.signatureStories || 0} · experience {counts.experience || 0}
        </p>
      </div>

      <div className="grid-two" style={{ marginTop: "1rem" }}>
        <div className="panel">
          <h2>Experience</h2>
          {(truth?.experience || []).map((exp) => (
            <div className="truth-block" key={exp.id || `${exp.org}-${exp.role}`}>
              <strong>
                {exp.org} — {exp.role}
              </strong>
              <div className="muted">{exp.dates}</div>
            </div>
          ))}
          <h2 style={{ marginTop: "1.25rem" }}>Metrics</h2>
          {(truth?.metrics || []).map((m) => (
            <div className="truth-block" key={m.id || m.text}>
              {m.text}
            </div>
          ))}
          <h2 style={{ marginTop: "1.25rem" }}>Never claim</h2>
          {(truth?.neverClaim || []).map((n) => (
            <div className="truth-block" key={n}>
              {n}
            </div>
          ))}
        </div>

        <div className="panel">
          <h2>Blurbs</h2>
          {(truth?.blurbs || []).map((b) => (
            <div className="truth-block" key={b.id || b.text}>
              <strong>{b.label || "Blurb"}</strong>
              <div>{b.text}</div>
              {b.id ? (
                <div className="actions">
                  <button
                    className="btn danger"
                    type="button"
                    disabled={busy}
                    onClick={() => removeBlurb(b.id!)}
                  >
                    Remove
                  </button>
                </div>
              ) : null}
            </div>
          ))}
          <form onSubmit={addBlurb} style={{ marginTop: "1rem" }}>
            <div className="field">
              <label htmlFor="blurb">Add blurb</label>
              <textarea
                id="blurb"
                value={blurb}
                onChange={(e) => setBlurb(e.target.value)}
                required
              />
            </div>
            <div className="actions">
              <button className="btn" type="submit" disabled={busy}>
                Add to bank
              </button>
            </div>
          </form>

          <h2 style={{ marginTop: "1.25rem" }}>Signature stories</h2>
          {(truth?.signatureStories || []).map((s) => (
            <div className="truth-block" key={s.id || s.title}>
              <strong>{s.title}</strong>
              <div className="muted">{s.body}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
