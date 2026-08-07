import type { Metadata } from "next";
import { Fraunces, Figtree } from "next/font/google";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <head>
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
        <div className="app-shell">
          <header className="topbar">
            <Link className="brand" href="/">
              Spruc<span>er</span>
            </Link>
            <SiteNav />
          </header>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
