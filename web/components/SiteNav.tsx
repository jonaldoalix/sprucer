"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

const pageLinks = [
  { href: "/applications", label: "Applications" },
  { href: "/fit", label: "Career fit" },
  { href: "/knowledge", label: "Knowledge" },
];

type AuthState =
  | { status: "loading" }
  | { status: "anonymous"; mode: string }
  | { status: "signed-in"; subject: string; mode: string };

export function SiteNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const cfg = (await apiFetch("/v1/auth/config")) as { mode?: string };
      const mode = String(cfg.mode || "dev");
      if (mode === "none") {
        setAuth({ status: "anonymous", mode });
        return;
      }
      try {
        const me = (await apiFetch("/v1/auth/whoami")) as { subject?: string; mode?: string };
        setAuth({
          status: "signed-in",
          subject: String(me.subject || "user"),
          mode: String(me.mode || mode),
        });
      } catch {
        setAuth({ status: "anonymous", mode });
      }
    } catch {
      setAuth({ status: "anonymous", mode: "unknown" });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, pathname]);

  async function logout() {
    setBusy(true);
    try {
      await apiFetch("/v1/auth/logout", { method: "POST", body: "{}" });
      setAuth({ status: "anonymous", mode: auth.status === "loading" ? "dev" : auth.mode });
      router.push("/login");
      router.refresh();
    } catch {
      // still flip UI; cookie may already be gone
      setAuth({ status: "anonymous", mode: "dev" });
      router.push("/login");
    } finally {
      setBusy(false);
    }
  }

  const showAuthControl = auth.status === "loading" || auth.mode !== "none";

  return (
    <nav className="nav">
      {pageLinks.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          data-active={pathname === link.href || pathname.startsWith(link.href + "/")}
        >
          {link.label}
        </Link>
      ))}
      {showAuthControl ? (
        auth.status === "signed-in" ? (
          <button
            type="button"
            className="nav-auth-btn"
            onClick={() => void logout()}
            disabled={busy}
            title={`Signed in as ${auth.subject}`}
          >
            {busy ? "Signing out…" : "Logout"}
          </button>
        ) : (
          <Link href="/login" data-active={pathname === "/login"}>
            Login
          </Link>
        )
      ) : null}
    </nav>
  );
}
