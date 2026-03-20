#!/usr/bin/env python3
"""Initialize the production visit-funnel database."""

from __future__ import annotations

from db import DB_PATH, ensure_schema


def main() -> None:
    ensure_schema()
    print(f"SQLite initialized at {DB_PATH}")


if __name__ == "__main__":
    main()
