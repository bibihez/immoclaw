#!/usr/bin/env python3
"""Minimal SQLite store for the visit funnel."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


DB_PATH = Path(__file__).resolve().parents[1] / "immoclaw.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_schema() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                address TEXT NOT NULL,
                commune TEXT DEFAULT '',
                postcode TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                source TEXT DEFAULT 'manual',
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                language TEXT DEFAULT 'fr',
                status TEXT DEFAULT 'new',
                qualification_rating TEXT DEFAULT '',
                budget INTEGER,
                financing_status TEXT DEFAULT '',
                preferred_days TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                form_sent_at TEXT DEFAULT '',
                qualified_at TEXT DEFAULT '',
                visit_proposed_at TEXT DEFAULT '',
                scheduled_at TEXT DEFAULT '',
                calcom_booking_uid TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (property_id) REFERENCES properties(id)
            );

            CREATE TABLE IF NOT EXISTS visits (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT DEFAULT '',
                status TEXT DEFAULT 'scheduled',
                source TEXT DEFAULT 'calcom',
                calcom_booking_uid TEXT DEFAULT '',
                location TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (property_id) REFERENCES properties(id)
            );

            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT DEFAULT '',
                property_id TEXT DEFAULT '',
                direction TEXT NOT NULL,
                recipient TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                provider_message_id TEXT DEFAULT '',
                status TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS webhook_events (
                provider TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_type TEXT DEFAULT '',
                object_uid TEXT DEFAULT '',
                status TEXT DEFAULT 'received',
                payload_json TEXT DEFAULT '',
                received_at TEXT NOT NULL,
                processed_at TEXT DEFAULT '',
                PRIMARY KEY (provider, event_id)
            );
            """
        )


def create_or_get_property(
    *,
    property_id: str = "",
    address: str,
    commune: str = "",
    postcode: str = "",
    notes: str = "",
) -> str:
    ensure_schema()
    property_id = property_id or gen_id("prop")
    timestamp = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM properties WHERE id = ?", (property_id,)).fetchone()
        if existing:
            return property_id
        conn.execute(
            """
            INSERT INTO properties (id, address, commune, postcode, status, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (property_id, address, commune, postcode, notes, timestamp, timestamp),
        )
    return property_id


def create_lead(
    *,
    property_id: str,
    name: str,
    phone: str = "",
    email: str = "",
    source: str = "immoweb",
    language: str = "fr",
    budget: int | None = None,
    notes: str = "",
) -> str:
    ensure_schema()
    lead_id = gen_id("lead")
    timestamp = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO leads (
                id, property_id, source, name, phone, email, language, status, budget, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)
            """,
            (lead_id, property_id, source, name, phone, email, language, budget, notes, timestamp, timestamp),
        )
    return lead_id


def update_lead(
    lead_id: str,
    *,
    status: str | None = None,
    qualification_rating: str | None = None,
    budget: int | None = None,
    financing_status: str | None = None,
    preferred_days: str | None = None,
    scheduled_at: str | None = None,
    calcom_booking_uid: str | None = None,
    notes: str | None = None,
    form_sent_at: str | None = None,
    qualified_at: str | None = None,
    visit_proposed_at: str | None = None,
) -> None:
    ensure_schema()
    updates: list[str] = []
    values: list[str] = []
    for field, value in (
        ("status", status),
        ("qualification_rating", qualification_rating),
        ("budget", budget),
        ("financing_status", financing_status),
        ("preferred_days", preferred_days),
        ("scheduled_at", scheduled_at),
        ("calcom_booking_uid", calcom_booking_uid),
        ("notes", notes),
        ("form_sent_at", form_sent_at),
        ("qualified_at", qualified_at),
        ("visit_proposed_at", visit_proposed_at),
    ):
        if value is not None:
            updates.append(f"{field} = ?")
            values.append(value)

    updates.append("updated_at = ?")
    values.append(now_iso())
    values.append(lead_id)

    with connect() as conn:
        conn.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id = ?", values)


def record_visit(
    *,
    lead_id: str,
    property_id: str,
    starts_at: str,
    ends_at: str = "",
    status: str = "scheduled",
    source: str = "calcom",
    calcom_booking_uid: str = "",
    location: str = "",
    notes: str = "",
) -> str:
    ensure_schema()
    visit_id = gen_id("visit")
    timestamp = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO visits (
                id, lead_id, property_id, starts_at, ends_at, status, source,
                calcom_booking_uid, location, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                visit_id,
                lead_id,
                property_id,
                starts_at,
                ends_at,
                status,
                source,
                calcom_booking_uid,
                location,
                notes,
                timestamp,
                timestamp,
            ),
        )
    return visit_id


def log_email(
    *,
    lead_id: str = "",
    property_id: str = "",
    direction: str,
    recipient: str = "",
    subject: str = "",
    provider_message_id: str = "",
    status: str = "",
) -> None:
    ensure_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO email_log (
                lead_id, property_id, direction, recipient, subject, provider_message_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (lead_id, property_id, direction, recipient, subject, provider_message_id, status, now_iso()),
        )


def get_lead(lead_id: str) -> dict[str, str] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def get_property(property_id: str) -> dict[str, str] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    return dict(row) if row else None


def list_leads(*, statuses: tuple[str, ...] = (), only_unscheduled: bool = False) -> list[dict[str, str]]:
    ensure_schema()
    query = "SELECT * FROM leads WHERE 1=1"
    values: list[str] = []
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        query += f" AND status IN ({placeholders})"
        values.extend(statuses)
    if only_unscheduled:
        query += " AND (scheduled_at = '' OR scheduled_at IS NULL)"
    query += " ORDER BY created_at ASC"
    with connect() as conn:
        rows = conn.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def list_visits(*, day_prefix: str = "", statuses: tuple[str, ...] = ()) -> list[dict[str, str]]:
    ensure_schema()
    query = "SELECT * FROM visits"
    values: list[str] = []
    where: list[str] = []
    if day_prefix:
        where.append("starts_at LIKE ?")
        values.append(f"{day_prefix}%")
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        where.append(f"status IN ({placeholders})")
        values.extend(statuses)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY starts_at ASC"
    with connect() as conn:
        rows = conn.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def update_visit(
    visit_id: str,
    *,
    starts_at: str | None = None,
    ends_at: str | None = None,
    status: str | None = None,
    calcom_booking_uid: str | None = None,
    notes: str | None = None,
) -> None:
    ensure_schema()
    updates: list[str] = []
    values: list[str] = []
    for field, value in (
        ("starts_at", starts_at),
        ("ends_at", ends_at),
        ("status", status),
        ("calcom_booking_uid", calcom_booking_uid),
        ("notes", notes),
    ):
        if value is not None:
            updates.append(f"{field} = ?")
            values.append(value)
    updates.append("updated_at = ?")
    values.append(now_iso())
    values.append(visit_id)
    with connect() as conn:
        conn.execute(f"UPDATE visits SET {', '.join(updates)} WHERE id = ?", values)


def find_visit_by_booking_uid(booking_uid: str) -> dict[str, str] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM visits
            WHERE calcom_booking_uid = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (booking_uid,),
        ).fetchone()
    return dict(row) if row else None


def store_webhook_event(
    *,
    provider: str,
    event_id: str,
    event_type: str = "",
    object_uid: str = "",
    payload: dict | None = None,
) -> bool:
    ensure_schema()
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO webhook_events (
                provider, event_id, event_type, object_uid, status, payload_json, received_at
            ) VALUES (?, ?, ?, ?, 'received', ?, ?)
            """,
            (provider, event_id, event_type, object_uid, payload_json, now_iso()),
        )
        return cursor.rowcount > 0


def mark_webhook_event_processed(provider: str, event_id: str, *, status: str = "processed") -> None:
    ensure_schema()
    with connect() as conn:
        conn.execute(
            """
            UPDATE webhook_events
            SET status = ?, processed_at = ?
            WHERE provider = ? AND event_id = ?
            """,
            (status, now_iso(), provider, event_id),
        )


def get_webhook_event(provider: str, event_id: str) -> dict[str, str] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM webhook_events WHERE provider = ? AND event_id = ?",
            (provider, event_id),
        ).fetchone()
    return dict(row) if row else None
