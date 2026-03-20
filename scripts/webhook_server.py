#!/usr/bin/env python3
"""Minimal HTTP webhook server for AgentMail and Cal.com."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from user_config import load_user_config
from webhook_ingest import handle_agentmail_event, handle_calcom_event


def _matches_signature(*, raw_body: bytes, secret: str, header_value: str) -> bool:
    if not secret:
        return True
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    candidates = {expected, f"sha256={expected}"}
    return header_value in candidates


def _build_handler(
    *,
    agentmail_path: str,
    calcom_path: str,
    agentmail_secret: str,
    calcom_secret: str,
    auto_process_leads: bool,
):
    class WebhookHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json_response(self, status_code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            raw_body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                self._json_response(400, {"error": "Invalid JSON"})
                return

            try:
                if self.path == agentmail_path:
                    header_value = self.headers.get("X-AgentMail-Signature", "")
                    if not _matches_signature(raw_body=raw_body, secret=agentmail_secret, header_value=header_value):
                        self._json_response(401, {"error": "Invalid AgentMail signature"})
                        return
                    result = handle_agentmail_event(payload, auto_process_leads=auto_process_leads)
                    self._json_response(200, result)
                    return

                if self.path == calcom_path:
                    header_value = self.headers.get("X-Cal-Signature-256", "")
                    if not _matches_signature(raw_body=raw_body, secret=calcom_secret, header_value=header_value):
                        self._json_response(401, {"error": "Invalid Cal.com signature"})
                        return
                    result = handle_calcom_event(payload)
                    self._json_response(200, result)
                    return

                self._json_response(404, {"error": "Unknown webhook path"})
            except Exception as exc:  # pragma: no cover - defensive runtime boundary
                self._json_response(500, {"error": str(exc)})

    return WebhookHandler


def main() -> None:
    cfg = load_user_config()
    parser = argparse.ArgumentParser(description="Serve AgentMail and Cal.com webhooks")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--agentmail-path", default="/webhooks/agentmail")
    parser.add_argument("--calcom-path", default="/webhooks/calcom")
    parser.add_argument("--auto-process-leads", action="store_true")
    args = parser.parse_args()

    handler = _build_handler(
        agentmail_path=args.agentmail_path,
        calcom_path=args.calcom_path,
        agentmail_secret=cfg.agentmail_webhook_secret,
        calcom_secret=cfg.calcom_webhook_secret,
        auto_process_leads=args.auto_process_leads,
    )

    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "status": "listening",
                "host": args.host,
                "port": args.port,
                "agentmail_path": args.agentmail_path,
                "calcom_path": args.calcom_path,
                "auto_process_leads": args.auto_process_leads,
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
