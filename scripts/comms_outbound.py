#!/usr/bin/env python3
"""Minimal outbound email helper built on top of the agentmail skill."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SendResult:
    success: bool
    sent_to: str = ""
    error: str = ""
    raw: str = ""


def _agentmail_send_script() -> Path:
    return Path(__file__).resolve().parents[1] / "skills" / "agentmail" / "scripts" / "send_email.py"


def send_email(
    *,
    inbox_id: str,
    to_email: str,
    subject: str,
    text: str,
    test_mode: bool = False,
    test_email: str = "",
    original_recipient_note: str | None = None,
    agentmail_api_key: str = "",
) -> SendResult:
    actual_recipient = test_email if (test_mode and test_email) else to_email
    body = text
    if test_mode:
        note = original_recipient_note or f"[TEST MODE] Email intended for: {to_email}"
        body = f"{body}\n\n---\n{note}"

    script_path = _agentmail_send_script()
    python_bin = "python3"
    cmd = [
        python_bin,
        str(script_path),
        "--inbox",
        inbox_id,
        "--to",
        actual_recipient,
        "--subject",
        subject,
        "--text",
        body,
    ]

    try:
        env = os.environ.copy()
        if agentmail_api_key and not env.get("AGENTMAIL_API_KEY"):
            env["AGENTMAIL_API_KEY"] = agentmail_api_key
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        if proc.returncode == 0:
            return SendResult(success=True, sent_to=actual_recipient, raw=proc.stdout.strip())
        return SendResult(
            success=False,
            sent_to=actual_recipient,
            error=proc.stderr.strip() or proc.stdout.strip(),
            raw=proc.stdout.strip(),
        )
    except Exception as exc:
        return SendResult(success=False, sent_to=actual_recipient, error=str(exc))
