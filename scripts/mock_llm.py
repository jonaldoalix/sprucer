#!/usr/bin/env python3
"""Local mock OpenAI-compatible chat endpoint for Sprucer demos (not for production)."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


REPLY = """## cover

I am applying for this role with facts drawn only from the provided career truth.

At Northwind Labs I own CI and deploy pipelines, and I cut average PR time-to-prod from 2 days to under 4 hours. That maps directly to your need for safer, faster pull-request-to-production paths.

## email

Subject: Application — Senior Platform Engineer

Hello,

I am writing about the Senior Platform Engineer role. My recent work centers on CI/CD ownership, reliability, and developer experience. Happy to share a tailored resume section and talk through a recent deploy-risk decision.

Thanks,
Alex

## Emphasis

- metric-pr-speed
- exp-northwind
- blurb-dx
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        return

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith("/v1/models") or self.path.startswith("/models"):
            self._json(200, {"data": [{"id": "mock-sprucer", "object": "model"}]})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        _ = self.rfile.read(length) if length else b""
        if "/chat/completions" in self.path:
            self._json(
                200,
                {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": REPLY},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
            return
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    host, port = "127.0.0.1", 4000
    print(f"mock llm on http://{host}:{port}/v1", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
