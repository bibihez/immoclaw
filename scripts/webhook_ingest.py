#!/usr/bin/env python3
"""Ingest AgentMail and Cal.com webhook payloads with idempotence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from db import (
    find_visit_by_booking_uid,
    get_lead,
    get_webhook_event,
    log_email,
    mark_webhook_event_processed,
    record_visit,
    store_webhook_event,
    update_lead,
    update_visit,
)
from poll_inbox import classify_email
from process_lead import process_lead


def _load_payload(path: str = "") -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    return json.loads(raw)


def _first_email(value: Any) -> str:
    if isinstance(value, list) and value:
        item = value[0] or {}
        if isinstance(item, dict):
            return str(item.get("email") or "")
    if isinstance(value, dict):
        return str(value.get("email") or "")
    return ""


def _stringify_list(values: Any) -> str:
    if isinstance(values, list):
        return ", ".join(str(item) for item in values if item)
    return str(values or "")


def _stable_event_id(provider: str, payload: dict[str, Any]) -> str:
    if provider == "agentmail":
        seed = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return f"agentmail_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"
    booking = payload.get("payload") or {}
    base = "|".join(
        [
            str(payload.get("triggerEvent") or ""),
            str(payload.get("createdAt") or ""),
            str(booking.get("uid") or ""),
            str(booking.get("startTime") or ""),
        ]
    )
    if not base.strip("|"):
        base = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"calcom_{hashlib.sha256(base.encode('utf-8')).hexdigest()[:24]}"


def _extract_calcom_value(booking_payload: dict[str, Any], key: str) -> str:
    metadata = booking_payload.get("metadata") or {}
    if metadata.get(key):
        return str(metadata[key])

    custom_inputs = booking_payload.get("customInputs") or {}
    if custom_inputs.get(key):
        return str(custom_inputs[key])

    responses = booking_payload.get("responses") or {}
    value = responses.get(key)
    if isinstance(value, dict):
        if value.get("value") not in (None, ""):
            return str(value["value"])
        if value.get("label") == key and value.get("value") not in (None, ""):
            return str(value["value"])
    for response_value in responses.values():
        if isinstance(response_value, dict) and response_value.get("label") == key and response_value.get("value") not in (None, ""):
            return str(response_value["value"])
    return ""


def handle_agentmail_event(payload: dict[str, Any], *, dry_run: bool = False, auto_process_leads: bool = False) -> dict[str, Any]:
    event_type = str(payload.get("event_type") or "")
    message = payload.get("message") or {}
    send = payload.get("send") or {}
    bounce = payload.get("bounce") or {}
    message_id = str(message.get("message_id") or send.get("message_id") or "")
    event_id = str(payload.get("event_id") or message_id or _stable_event_id("agentmail", payload))

    if not dry_run and not store_webhook_event(
        provider="agentmail",
        event_id=event_id,
        event_type=event_type,
        object_uid=message_id,
        payload=payload,
    ):
        duplicate = get_webhook_event("agentmail", event_id) or {}
        return {"provider": "agentmail", "event_id": event_id, "duplicate": True, "status": duplicate.get("status", "processed")}

    result: dict[str, Any] = {
        "provider": "agentmail",
        "event_id": event_id,
        "event_type": event_type,
        "message_id": message_id,
        "duplicate": False,
    }

    if event_type == "message.received":
        from_addr = _first_email(message.get("from"))
        subject = str(message.get("subject") or "")
        body = str(message.get("text") or message.get("extracted_text") or message.get("preview") or "")
        classification = classify_email(from_addr, subject, body)
        process_result = None
        lead_id = ""
        property_id = ""
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
                    part
                    for part in [lead.get("street", ""), f"{lead.get('postcode', '')} {lead.get('commune', '')}".strip()]
                    if part
                ),
            )
            lead_id = str(process_result.get("lead_id") or "")
            property_id = str(process_result.get("property_id") or "")

        if not dry_run:
            log_email(
                lead_id=lead_id,
                property_id=property_id,
                direction="inbound",
                recipient=from_addr,
                subject=subject,
                provider_message_id=message_id,
                status="received",
            )
            mark_webhook_event_processed("agentmail", event_id)

        result.update(
            {
                "action": "classified_message",
                "classification": classification,
                "processed_lead": process_result,
            }
        )
        return result

    if event_type == "message.sent":
        recipients = _stringify_list(send.get("recipients"))
        if not dry_run:
            log_email(
                direction="outbound",
                recipient=recipients,
                subject="",
                provider_message_id=message_id,
                status="sent",
            )
            mark_webhook_event_processed("agentmail", event_id)
        result.update({"action": "logged_sent_message", "recipients": recipients})
        return result

    if event_type in {"message.delivered", "message.bounced", "message.complained"}:
        recipients = _stringify_list(send.get("recipients") or [item.get("address", "") for item in bounce.get("recipients", [])])
        status = event_type.split(".", 1)[-1]
        if not dry_run:
            log_email(
                direction="outbound",
                recipient=recipients,
                subject="",
                provider_message_id=message_id,
                status=status,
            )
            mark_webhook_event_processed("agentmail", event_id, status=status)
        result.update({"action": "logged_delivery_event", "delivery_status": status, "recipients": recipients})
        return result

    if not dry_run:
        mark_webhook_event_processed("agentmail", event_id, status="ignored")
    result.update({"action": "ignored"})
    return result


def handle_calcom_event(payload: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    event_type = str(payload.get("triggerEvent") or "")
    booking = payload.get("payload") or {}
    booking_uid = str(booking.get("uid") or "")
    event_id = str(payload.get("event_id") or _stable_event_id("calcom", payload))

    if not dry_run and not store_webhook_event(
        provider="calcom",
        event_id=event_id,
        event_type=event_type,
        object_uid=booking_uid,
        payload=payload,
    ):
        duplicate = get_webhook_event("calcom", event_id) or {}
        return {"provider": "calcom", "event_id": event_id, "duplicate": True, "status": duplicate.get("status", "processed")}

    visit = find_visit_by_booking_uid(booking_uid) if booking_uid else None
    lead_id = _extract_calcom_value(booking, "lead_id")
    property_id = _extract_calcom_value(booking, "property_id")
    starts_at = str(booking.get("startTime") or booking.get("start") or "")
    result: dict[str, Any] = {
        "provider": "calcom",
        "event_id": event_id,
        "event_type": event_type,
        "booking_uid": booking_uid,
        "duplicate": False,
    }

    if event_type in {"BOOKING_CREATED", "BOOKING_CONFIRMED"}:
        if visit:
            if not dry_run:
                update_visit(visit["id"], starts_at=starts_at or None, status="scheduled")
                update_lead(visit["lead_id"], status="visit_scheduled", scheduled_at=starts_at or visit["starts_at"], calcom_booking_uid=booking_uid)
                mark_webhook_event_processed("calcom", event_id)
            result.update({"action": "synced_existing_visit", "visit_id": visit["id"]})
            return result

        if lead_id and property_id and starts_at and get_lead(lead_id):
            visit_id = ""
            if not dry_run:
                visit_id = record_visit(
                    lead_id=lead_id,
                    property_id=property_id,
                    starts_at=starts_at,
                    status="scheduled",
                    source="calcom_webhook",
                    calcom_booking_uid=booking_uid,
                    location=str(booking.get("location") or ""),
                    notes="Synced from Cal.com webhook",
                )
                update_lead(lead_id, status="visit_scheduled", scheduled_at=starts_at, calcom_booking_uid=booking_uid)
                mark_webhook_event_processed("calcom", event_id)
            result.update({"action": "created_visit_from_webhook", "visit_id": visit_id or "dry_run"})
            return result

        if not dry_run:
            mark_webhook_event_processed("calcom", event_id, status="ignored")
        result.update({"action": "ignored_unknown_booking"})
        return result

    if event_type == "BOOKING_RESCHEDULED":
        if not visit:
            if not dry_run:
                mark_webhook_event_processed("calcom", event_id, status="ignored")
            result.update({"action": "ignored_missing_visit"})
            return result
        if not dry_run:
            update_visit(visit["id"], starts_at=starts_at or None, status="rescheduled")
            update_lead(visit["lead_id"], status="visit_scheduled", scheduled_at=starts_at or visit["starts_at"])
            mark_webhook_event_processed("calcom", event_id)
        result.update({"action": "rescheduled_visit", "visit_id": visit["id"]})
        return result

    if event_type in {"BOOKING_CANCELLED", "BOOKING_REJECTED"}:
        if not visit:
            if not dry_run:
                mark_webhook_event_processed("calcom", event_id, status="ignored")
            result.update({"action": "ignored_missing_visit"})
            return result
        reason = str(booking.get("cancellationReason") or booking.get("rejectionReason") or "")
        mapped_status = "cancelled" if event_type == "BOOKING_CANCELLED" else "rejected"
        if not dry_run:
            update_visit(visit["id"], status=mapped_status, notes=reason or mapped_status.title())
            update_lead(visit["lead_id"], status="qualified", scheduled_at="", calcom_booking_uid="")
            mark_webhook_event_processed("calcom", event_id, status=mapped_status)
        result.update({"action": f"{mapped_status}_visit", "visit_id": visit["id"]})
        return result

    if event_type == "MEETING_ENDED":
        if not visit:
            if not dry_run:
                mark_webhook_event_processed("calcom", event_id, status="ignored")
            result.update({"action": "ignored_missing_visit"})
            return result
        if not dry_run:
            update_visit(visit["id"], status="completed")
            update_lead(visit["lead_id"], status="visited")
            mark_webhook_event_processed("calcom", event_id, status="completed")
        result.update({"action": "completed_visit", "visit_id": visit["id"]})
        return result

    if not dry_run:
        mark_webhook_event_processed("calcom", event_id, status="ignored")
    result.update({"action": "ignored"})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest webhook payloads from AgentMail or Cal.com")
    sub = parser.add_subparsers(dest="provider", required=True)

    agentmail = sub.add_parser("agentmail")
    agentmail.add_argument("--file", default="")
    agentmail.add_argument("--dry-run", action="store_true")
    agentmail.add_argument("--auto-process-leads", action="store_true")

    calcom = sub.add_parser("calcom")
    calcom.add_argument("--file", default="")
    calcom.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    payload = _load_payload(args.file)
    if args.provider == "agentmail":
        result = handle_agentmail_event(
            payload,
            dry_run=args.dry_run,
            auto_process_leads=args.auto_process_leads,
        )
    else:
        result = handle_calcom_event(payload, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
