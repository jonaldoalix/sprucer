export function apiBase(): string {
  // Browser: same-origin via Next.js rewrites (keeps session cookies reliable).
  if (typeof window !== "undefined") {
    return "";
  }
  return (
    process.env.SPRUCER_PUBLIC_URL ||
    process.env.NEXT_PUBLIC_SPRUCER_API_URL ||
    "http://127.0.0.1:8787"
  );
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  const text = await res.text();
  let json: Record<string, unknown> = {};
  try {
    json = text.trim() ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {
    const snippet = text.replace(/\s+/g, " ").trim().slice(0, 80);
    throw new Error(
      `Non-JSON response from API (${res.status})${snippet ? `: ${snippet}` : ""}. ` +
        (res.status >= 500
          ? "The web proxy or brain may have timed out — try Generate again."
          : "Check that the Sprucer brain is running."),
    );
  }
  if (!res.ok) {
    throw new Error(String(json.detail || json.error || `HTTP ${res.status}`));
  }
  return json;
}
