#!/usr/bin/env python3
"""Poll AgentMail, classify inbound emails, and optionally create leads."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from process_lead import process_lead
from user_config import load_user_config


STATE_DIR = Path(__file__).resolve().parents[1] / "state"
SEEN_PATH = STATE_DIR / "agentmail_seen.json"


def parse_immoweb_lead(body: str) -> dict[str, Any]:
    lead: dict[str, Any] = {}
    patterns = {
        "name": r"\*?\s*Nom\s*\*?\s*[:\uff1a]\s*\*?\s*(.+?)(?:\n|$)",
        "email": r"\*?\s*Adresse\s+mail\s*\*?\s*[:\uff1a]\s*\*?\s*(\S+@\S+)",
        "phone": r"\*?\s*T[eé]l[eé]phone\s*\*?\s*[:\uff1a]\s*\*?\s*([\d\s\+]+)",
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, body)
        if match:
            value = match.group(1).strip().strip("*").rstrip(",")
            if field == "phone":
                value = re.sub(r"\s+", "", value)
            lead[field] = value

    price = re.search(r"([\d\s\.]+)\s*€", body)
    if price:
        lead["price"] = int(re.sub(r"[\s\.]", "", price.group(1)))

    postal_city = re.search(r"(\d{4})\s+([A-Za-zÀ-ÿ\-]+)", body)
    if postal_city:
        lead["postcode"] = postal_city.group(1)
        lead["commune"] = postal_city.group(2)

    street = re.search(r"^\s*(?:Bien|Adresse du bien|Adresse)\s*[:\uff1a]\s*(.+?)\s*$", body, re.IGNORECASE | re.MULTILINE)
    if not street:
        street = re.search(
            r"([^\n]*(?:rue|avenue|chaussée|straat|laan|place|plein)[^\n]*)",
            body,
            re.IGNORECASE,
        )
    if street:
        lead["street"] = street.group(1).strip()

    return lead


def classify_email(from_addr: str, subject: str, body: str) -> dict[str, Any]:
    from_lower = (from_addr or "").lower()
    subject_lower = (subject or "").lower()

    if "immoweb" in from_lower or "immoweb" in subject_lower:
        return {
            "skill": "visits",
            "message_type": "new_lead",
            "lead_data": parse_immoweb_lead(body or ""),
            "reason": "Immoweb lead detected",
        }

    if any(word in subject_lower for word in ["offre", "bod", "offer"]):
        return {"skill": "offers", "message_type": "offer", "lead_data": {}, "reason": "Offer keyword match"}
    if any(word in subject_lower for word in ["visite", "bezoek", "visit"]):
        return {"skill": "visits", "message_type": "visit", "lead_data": {}, "reason": "Visit keyword match"}
    if any(word in subject_lower for word in ["peb", "epc", "urbanisme", "compromis", "notaire", "syndic"]):
        return {"skill": "dossier", "message_type": "document", "lead_data": {}, "reason": "Document keyword match"}
    return {"skill": "unknown", "message_type": "unknown", "lead_data": {}, "reason": "No match"}


def _load_seen() -> dict[str, Any]:
    if not SEEN_PATH.exists():
        return {"seen": [], "updated_at": None}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": [], "updated_at": None}


def _save_seen(seen_ids: list[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"seen": seen_ids[-5000:], "updated_at": datetime.now(timezone.utc).isoformat()}
    SEEN_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _agentmail_get(path: str, *, api_key: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "immoclaw-poll/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AgentMail HTTP {exc.code}: {raw}") from exc


def process_inbox(*, limit: int = 20, dry_run: bool = False, auto_process_leads: bool = False) -> dict[str, Any]:
    cfg = load_user_config()
    api_key = cfg.agentmail_api_key
    inbox_id = cfg.agentmail_inbox_id
    base_url = "https://api.agentmail.to/v0"
    if not api_key:
        return {"error": "AGENTMAIL_API_KEY not set"}
    if not inbox_id:
        return {"error": "AGENTMAIL_INBOX_ID not set"}

    seen_state = _load_seen()
    seen_ids = [str(item) for item in seen_state.get("seen") or []]
    seen_set = set(seen_ids)
    listing = _agentmail_get(f"/inboxes/{inbox_id}/messages", api_key=api_key, base_url=base_url, params={"limit": limit})

    results: list[dict[str, Any]] = []
    new_seen = False

    for msg_item in listing.get("messages") or []:
        msg_id = str(msg_item.get("message_id") or "")
        if not msg_id or msg_id in seen_set:
            continue

        labels = [str(item).lower() for item in (msg_item.get("labels") or [])]
        if "sent" in labels and "unread" not in labels:
            if not dry_run:
                seen_ids.append(msg_id)
                seen_set.add(msg_id)
                new_seen = True
            continue

        msg_id_q = urllib.parse.quote(msg_id, safe="")
        full_msg = _agentmail_get(
            f"/inboxes/{inbox_id}/messages/{msg_id_q}",
            api_key=api_key,
            base_url=base_url,
        )

        from_field = full_msg.get("from") or msg_item.get("from") or []
        if isinstance(from_field, list) and from_field:
            from_addr = from_field[0].get("email") or ""
        else:
            from_addr = str(from_field)
        subject = full_msg.get("subject") or msg_item.get("subject") or ""
        body = full_msg.get("extracted_text") or full_msg.get("text") or msg_item.get("preview") or ""
        classification = classify_email(from_addr, subject, body)

        process_result = None
        if auto_process_leads and classification["skill"] == "visits" and classification["message_type"] == "new_lead":
            lead = classification["lead_data"]
            process_result = process_lead(
                name=lead.get("name", "Lead sans nom"),
                phone=lead.get("phone", ""),
                email=lead.get("email", ""),
                street=lead.get("street", ""),
                postcode=lead.get("postcode", ""),
                commune=lead.get("commune", ""),
                price=lead.get("price"),
                property_address=", ".join(
                    part for part in [lead.get("street", ""), f"{lead.get('postcode', '')} {lead.get('commune', '')}".strip()] if part
                ),
            )

        results.append(
            {
                "message_id": msg_id,
                "from": from_addr,
                "subject": subject,
                "classification": classification,
                "processed_lead": process_result,
                "timestamp": full_msg.get("timestamp") or msg_item.get("timestamp"),
            }
        )

        if not dry_run:
            seen_ids.append(msg_id)
            seen_set.add(msg_id)
            new_seen = True

    if not dry_run and new_seen:
        _save_seen(seen_ids)

    return {
        "inbox": inbox_id,
        "processed": len(results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll AgentMail and optionally process new leads")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--auto-process-leads", action="store_true")
    args = parser.parse_args()
    result = process_inbox(limit=args.limit, dry_run=args.dry_run, auto_process_leads=args.auto_process_leads)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
