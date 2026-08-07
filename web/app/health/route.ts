import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const brain = (process.env.SPRUCER_PUBLIC_URL || "http://127.0.0.1:8787").replace(/\/$/, "");

/** Same-origin /health → brain health (replaces Next rewrite). */
export async function GET(_req: NextRequest) {
  try {
    const upstream = await fetch(`${brain}/health`, { cache: "no-store" });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "Brain unreachable" },
      { status: 502 },
    );
  }
}
