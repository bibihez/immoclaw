#!/usr/bin/env python3
"""Tiny template renderer for templates/*.md."""

from __future__ import annotations

from pathlib import Path


def render_template(path: str | Path, **vars: str) -> str:
    template_path = Path(path)
    text = template_path.read_text(encoding="utf-8")
    try:
        return text.format(**vars)
    except KeyError as exc:
        missing = str(exc).strip("'")
        raise KeyError(f"Missing template variable: {missing} for template {template_path}") from exc
