"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type AppRow = {
  id: string;
  company?: string;
  title?: string;
  status?: string;
  location?: string;
};

type Generation = {
  id: string;
  approval?: string;
  types?: string[];
  createdAt?: string;
};

type AppDetail = AppRow & {
  notes?: string;
  jdText?: string;
  generations?: Generation[];
  url?: string;
};

export default function ApplicationsPage() {
  const [items, setItems] = useState<AppRow[]>([]);
  const [selected, setSelected] = useState<AppDetail | null>(null);
  const [jd, setJd] = useState("");
  const [types, setTypes] = useState("cover,email");
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("draft");
  const [notes, setNotes] = useState("");

  const loadList = useCallback(async () => {
    const json = await apiFetch("/v1/applications");
    setItems((json.items as AppRow[]) || []);
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    const json = await apiFetch(`/v1/applications/${encodeURIComponent(id)}`);
    const app = json.application as AppDetail;
    setSelected(app);
    setStatus(app.status || "draft");
    setNotes(app.notes || "");
    setPreview("");
  }, []);

  useEffect(() => {
    loadList().catch((err) => setError(err instanceof Error ? err.message : "Load failed"));
  }, [loadList]);

  async function ingest(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const json = await apiFetch("/v1/jd/ingest", {
        method: "POST",
        body: JSON.stringify({ source_type: "paste", text: jd }),
      });
      const app = json.application as AppDetail;
      await loadList();
      await loadDetail(app.id);
      setJd("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const typeList = types
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const json = await apiFetch("/v1/generate", {
        method: "POST",
        body: JSON.stringify({ application_id: selected.id, types: typeList }),
      });
      setPreview(String(json.preview || ""));
      await loadDetail(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve(generationId: string) {
    if (!selected) return;
    if (!window.confirm("Approve this generation?")) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/v1/generations/approve", {
        method: "POST",
        body: JSON.stringify({
          application_id: selected.id,
          generation_id: generationId,
          confirm: true,
        }),
      });
      const full = await apiFetch(
        `/v1/applications/${encodeURIComponent(selected.id)}/generations/${encodeURIComponent(generationId)}`,
      );
      setPreview(String(full.content || ""));
      await loadDetail(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveMeta() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/v1/applications", {
        method: "POST",
        body: JSON.stringify({ id: selected.id, status, notes }),
      });
      await loadList();
      await loadDetail(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function openGeneration(generationId: string) {
    if (!selected) return;
    try {
      const full = await apiFetch(
        `/v1/applications/${encodeURIComponent(selected.id)}/generations/${encodeURIComponent(generationId)}`,
      );
      setPreview(String(full.content || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load generation failed");
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Applications</h1>
        <p>Ingest a JD, generate drafts, track status, and approve before you send.</p>
      </section>

      {error ? <p className="error">{error}</p> : null}

      <div className="grid-two">
        <div className="panel">
          <h2>Tracker</h2>
          <ul className="list">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="row"
                  data-active={selected?.id === item.id}
                  onClick={() => loadDetail(item.id).catch((err) => setError(String(err)))}
                >
                  <strong>
                    {item.company || "Company"} — {item.title || "Role"}
                  </strong>
                  <span className="muted">
                    <span className="status">{item.status || "draft"}</span> · {item.id}
                  </span>
                </button>
              </li>
            ))}
            {!items.length ? <li className="muted">No applications yet.</li> : null}
          </ul>

          <form onSubmit={ingest} style={{ marginTop: "1.25rem" }}>
            <h2>Ingest JD</h2>
            <div className="field">
              <label htmlFor="jd">Paste job description</label>
              <textarea id="jd" value={jd} onChange={(e) => setJd(e.target.value)} required />
            </div>
            <div className="actions">
              <button className="btn" type="submit" disabled={busy}>
                Save application
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <h2>Detail</h2>
          {!selected ? (
            <p className="muted">Select an application or ingest a JD.</p>
          ) : (
            <>
              <p>
                <strong>
                  {selected.company || "Company"} — {selected.title || "Role"}
                </strong>
                <br />
                <span className="muted">{selected.location || "Location unknown"}</span>
              </p>
              <div className="field">
                <label htmlFor="status">Status</label>
                <select id="status" value={status} onChange={(e) => setStatus(e.target.value)}>
                  {["draft", "applied", "interview", "offer", "rejected", "withdrawn"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="notes">Notes</label>
                <textarea id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
              <div className="actions">
                <button className="btn secondary" type="button" onClick={saveMeta} disabled={busy}>
                  Save status
                </button>
              </div>

              <div className="field" style={{ marginTop: "1rem" }}>
                <label htmlFor="types">Generate types</label>
                <input id="types" value={types} onChange={(e) => setTypes(e.target.value)} />
              </div>
              <div className="actions">
                <button className="btn" type="button" onClick={generate} disabled={busy}>
                  Generate draft
                </button>
              </div>

              <h2 style={{ marginTop: "1.25rem" }}>Generations</h2>
              <ul className="list">
                {(selected.generations || []).map((g) => (
                  <li key={g.id}>
                    <button type="button" className="row" onClick={() => openGeneration(g.id)}>
                      <strong>{g.id}</strong>
                      <span className="muted">
                        <span className="status">{g.approval || "draft"}</span> ·{" "}
                        {(g.types || []).join(", ")}
                      </span>
                    </button>
                    {g.approval !== "approved" ? (
                      <div className="actions">
                        <button
                          className="btn secondary"
                          type="button"
                          disabled={busy}
                          onClick={() => approve(g.id)}
                        >
                          Approve
                        </button>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>

              {preview ? (
                <>
                  <h2 style={{ marginTop: "1rem" }}>Preview</h2>
                  <pre className="markdown">{preview}</pre>
                </>
              ) : null}
            </>
          )}
        </div>
      </div>
    </>
  );
}
