import type { Metadata } from "next";
import { Fraunces, Figtree } from "next/font/google";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
import { ThemeToggle } from "@/components/ThemeToggle";
import { DemoBar } from "@/components/DemoBar";
import { DemoGate } from "@/components/DemoGate";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display-loaded",
  weight: ["500", "600", "700"],
});

const body = Figtree({
  subsets: ["latin"],
  variable: "--font-body-loaded",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Sprucer",
  description: "Truth-first application materials desk",
};

const themeBootScript = `(function(){try{var k="sprucer-theme";var t=localStorage.getItem(k);var pref=(t==="system"||t==="light"||t==="neutral"||t==="dark")?t:"system";var resolved=pref==="system"?(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):pref;document.documentElement.setAttribute("data-theme",resolved);document.documentElement.setAttribute("data-theme-pref",pref);}catch(e){document.documentElement.setAttribute("data-theme","light");document.documentElement.setAttribute("data-theme-pref","system");}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
        <link rel="stylesheet" href="/theme.override.css" />
      </head>
      <body
        style={
          {
            ["--font-display" as string]: "var(--font-display-loaded), serif",
            ["--font-body" as string]: "var(--font-body-loaded), sans-serif",
          } as React.CSSProperties
        }
      >
        <DemoGate />
        <div className="app-shell">
          <header className="topbar">
            <Link className="brand" href="/">
              Spruc<span>er</span>
            </Link>
            <div className="topbar-right">
              <ThemeToggle />
              <SiteNav />
            </div>
          </header>
          <DemoBar />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
