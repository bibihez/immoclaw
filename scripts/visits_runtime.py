#!/usr/bin/env python3
"""Runtime commands for the core visit funnel."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from calcom_client import CalcomClient
from db import (
    find_visit_by_booking_uid,
    get_lead,
    get_property,
    list_visits,
    now_iso,
    record_visit,
    update_lead,
    update_visit,
)
from user_config import load_user_config


DAY_NAME_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "lundi": "mon",
    "maandag": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "mardi": "tue",
    "dinsdag": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "mercredi": "wed",
    "woensdag": "wed",
    "thu": "thu",
    "thursday": "thu",
    "jeudi": "thu",
    "donderdag": "thu",
    "fri": "fri",
    "friday": "fri",
    "vendredi": "fri",
    "vrijdag": "fri",
    "sat": "sat",
    "saturday": "sat",
    "samedi": "sat",
    "zaterdag": "sat",
    "sun": "sun",
    "sunday": "sun",
    "dimanche": "sun",
    "zondag": "sun",
}

DAY_PART_ALIASES = {
    "morning": "am",
    "matin": "am",
    "voormiddag": "am",
    "afternoon": "pm",
    "apres midi": "pm",
    "apres-midi": "pm",
    "apresmidi": "pm",
    "namiddag": "pm",
}


def fold_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[\s_/]+", " ", ascii_only.replace("–", "-").replace("—", "-").strip().lower())
    return re.sub(r"\s+", " ", collapsed)


def parse_preferred_day_parts(raw: str) -> set[str]:
    folded = fold_text(raw)
    if not folded:
        return set()
    day_hits = {code for token, code in DAY_NAME_ALIASES.items() if token in folded}
    part_hits = {code for token, code in DAY_PART_ALIASES.items() if token in folded}
    if not day_hits:
        return set()
    if not part_hits:
        return {f"{day}_am" for day in day_hits} | {f"{day}_pm" for day in day_hits}
    return {f"{day}_{part}" for day in day_hits for part in part_hits}


def slot_code(start_iso: str) -> str:
    dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    day_code = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][dt.weekday()]
    part_code = "am" if dt.hour < 12 else "pm"
    return f"{day_code}_{part_code}"


def normalize_financing(raw: str) -> str:
    folded = fold_text(raw)
    if any(token in folded for token in ["accord de principe", "pre approved", "principieel akkoord"]):
        return "pre_approved"
    if any(token in folded for token in ["en cours", "in progress", "demande", "aanvraag"]):
        return "in_progress"
    if any(token in folded for token in ["fonds propres", "own funds", "eigen middelen"]):
        return "own_funds"
    if any(token in folded for token in ["pas encore", "not started", "nog niet"]):
        return "not_started"
    return ""


def normalize_timing(raw: str) -> str:
    folded = fold_text(raw)
    if any(token in folded for token in ["1 a 3 mois", "1-3 months", "1 tot 3 maanden"]):
        return "1_3_months"
    if any(token in folded for token in ["moins d", "less than 1 month", "minder dan een maand"]):
        return "lt_1_month"
    if any(token in folded for token in ["3 a 6 mois", "3-6 months", "3 tot 6 maanden"]):
        return "3_6_months"
    if any(token in folded for token in ["pas de rush", "no rush", "geen haast"]):
        return "no_rush"
    return ""


def parse_budget(raw: str) -> int | None:
    numbers = []
    for chunk in re.findall(r"\d[\d\s\.]*", str(raw)):
        digits = re.sub(r"\D", "", chunk)
        if len(digits) >= 4:
            numbers.append(int(digits))
    if not numbers:
        return None
    if len(numbers) == 1:
        return numbers[0]
    return int(sum(numbers[:2]) / 2)


def evaluate_qualification(reply: dict[str, Any], property_price: int | None = None) -> dict[str, Any]:
    budget = parse_budget(str(reply.get("budget", "")))
    financing_status = normalize_financing(str(reply.get("financing_status", "")))
    timing = normalize_timing(str(reply.get("timing", "")))
    motivation = fold_text(reply.get("motivation", ""))
    preferred_days = str(reply.get("preferred_days", "")).strip()

    score = 0
    if budget and property_price and budget >= int(property_price * 0.9):
        score += 2
    elif budget:
        score += 1

    if financing_status in {"pre_approved", "own_funds"}:
        score += 2
    elif financing_status == "in_progress":
        score += 1

    if timing in {"lt_1_month", "1_3_months"}:
        score += 2
    elif timing == "3_6_months":
        score += 1

    if motivation and len(motivation) > 25:
        score += 1

    if not motivation or "curieux" in motivation or "nieuwsgierig" in motivation:
        score -= 2

    if score >= 5:
        rating = "hot"
        status = "qualified"
    elif score >= 3:
        rating = "medium"
        status = "qualified"
    elif score >= 1:
        rating = "weak"
        status = "form_sent"
    else:
        rating = "reject"
        status = "closed"

    return {
        "qualification_rating": rating,
        "status": status,
        "budget": budget,
        "financing_status": financing_status,
        "timing": timing,
        "preferred_days": preferred_days,
    }


def flatten_slots(calcom_response: dict[str, Any]) -> list[dict[str, str]]:
    slots = ((calcom_response.get("data") or {}).get("slots") or {})
    flattened: list[dict[str, str]] = []
    for day_slots in slots.values():
        for item in day_slots:
            start = item.get("time")
            if start:
                flattened.append({"start": start, "end": ""})
    return sorted(flattened, key=lambda slot: slot["start"])


def choose_slots(slots: list[dict[str, str]], preferred_days: str, limit: int = 3) -> list[dict[str, str]]:
    preferred_codes = parse_preferred_day_parts(preferred_days)
    if preferred_codes:
        filtered = [slot for slot in slots if slot_code(slot["start"]) in preferred_codes]
        if filtered:
            return filtered[:limit]
    return slots[:limit]


def propose_slots(*, lead_id: str, days: int = 7, event_slug: str = "", slots_file: str = "") -> dict[str, Any]:
    lead = get_lead(lead_id)
    if not lead:
        raise RuntimeError(f"Lead not found: {lead_id}")
    if lead["status"] not in {"qualified", "visit_proposed"}:
        raise RuntimeError(f"Lead {lead_id} is not ready for slot proposals (status={lead['status']})")

    cfg = load_user_config()
    event_slug = event_slug or cfg.calcom_private_visit_event_slug
    if slots_file:
        with open(slots_file, "r", encoding="utf-8") as handle:
            response = json.load(handle)
    else:
        client = CalcomClient()
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=days)
        response = client.get_slots(
            event_slug=event_slug,
            start_time=start.isoformat() + "Z",
            end_time=end.isoformat() + "Z",
        )

    options = choose_slots(flatten_slots(response), lead.get("preferred_days", ""))
    if not options:
        raise RuntimeError("No available slots returned by Cal.com")

    update_lead(lead_id, status="visit_proposed", visit_proposed_at=now_iso())
    property_row = get_property(lead["property_id"]) or {}
    return {
        "lead_id": lead_id,
        "property_id": lead["property_id"],
        "address": property_row.get("address", ""),
        "best_slot": options[0],
        "alternatives": options[1:],
        "telegram_note": (
            f"[{property_row.get('address', 'Bien sans adresse')}] {lead['name']} est qualifié. "
            f"Meilleur créneau: {options[0]['start']}. OK pour proposer ?"
        ),
        "options": options,
    }


def book_visit(*, lead_id: str, start: str, event_slug: str = "", dry_run: bool = False) -> dict[str, Any]:
    lead = get_lead(lead_id)
    if not lead:
        raise RuntimeError(f"Lead not found: {lead_id}")
    property_row = get_property(lead["property_id"]) or {}
    cfg = load_user_config()
    event_slug = event_slug or cfg.calcom_private_visit_event_slug

    booking_fields = {
        "lead_id": lead_id,
        "property_id": lead["property_id"],
        "address": property_row.get("address", ""),
    }

    if dry_run:
        booking = {"status": "success", "data": {"uid": f"dry_run_{uuid.uuid4().hex[:12]}"}}
    else:
        booking = CalcomClient().create_booking(
            event_type_slug=event_slug,
            start=start,
            attendee_name=lead["name"],
            attendee_email=lead["email"],
            attendee_timezone="Europe/Brussels",
            booking_fields_responses=booking_fields,
        )

    booking_uid = ((booking.get("data") or {}).get("uid") or booking.get("uid") or "")
    visit_id = record_visit(
        lead_id=lead_id,
        property_id=lead["property_id"],
        starts_at=start,
        calcom_booking_uid=booking_uid,
        location=property_row.get("address", ""),
        notes="Booked through Cal.com",
    )
    update_lead(lead_id, status="visit_scheduled", scheduled_at=start, calcom_booking_uid=booking_uid)
    return {"lead_id": lead_id, "visit_id": visit_id, "booking_uid": booking_uid, "booking": booking}


def reschedule_visit(*, booking_uid: str, start: str, reason: str = "", dry_run: bool = False) -> dict[str, Any]:
    visit = find_visit_by_booking_uid(booking_uid)
    if not visit:
        raise RuntimeError(f"Visit not found for booking UID: {booking_uid}")
    response = {"status": "success", "data": {"uid": booking_uid}} if dry_run else CalcomClient().reschedule_booking(
        booking_uid=booking_uid,
        start=start,
        reason=reason,
    )
    update_visit(visit["id"], starts_at=start, status="rescheduled")
    update_lead(visit["lead_id"], status="visit_scheduled", scheduled_at=start)
    return {"visit_id": visit["id"], "booking_uid": booking_uid, "response": response}


def cancel_visit(*, booking_uid: str, reason: str = "", dry_run: bool = False) -> dict[str, Any]:
    visit = find_visit_by_booking_uid(booking_uid)
    if not visit:
        raise RuntimeError(f"Visit not found for booking UID: {booking_uid}")
    response = {"status": "success"} if dry_run else CalcomClient().cancel_booking(
        booking_uid=booking_uid,
        reason=reason,
    )
    update_visit(visit["id"], status="cancelled", notes=reason or "Cancelled")
    update_lead(visit["lead_id"], status="qualified", scheduled_at="", calcom_booking_uid="")
    return {"visit_id": visit["id"], "booking_uid": booking_uid, "response": response}


def build_briefings(*, target_date: str = "") -> dict[str, Any]:
    if not target_date:
        target_date = (date.today() + timedelta(days=1)).isoformat()
    cards = []
    for visit in list_visits(day_prefix=target_date, statuses=("scheduled", "rescheduled")):
        lead = get_lead(visit["lead_id"]) or {}
        property_row = get_property(visit["property_id"]) or {}
        cards.append(
            {
                "visit_id": visit["id"],
                "starts_at": visit["starts_at"],
                "address": property_row.get("address", ""),
                "lead_name": lead.get("name", ""),
                "lead_phone": lead.get("phone", ""),
                "qualification_rating": lead.get("qualification_rating", ""),
                "message": (
                    f"VISITE DEMAIN {visit['starts_at']} - {property_row.get('address', '')}\n"
                    f"Acheteur: {lead.get('name', '')} | Tel: {lead.get('phone', '')}\n"
                    f"Rating: {lead.get('qualification_rating', 'unknown')}"
                ),
            }
        )
    return {"date": target_date, "count": len(cards), "cards": cards}


def main() -> None:
    parser = argparse.ArgumentParser(description="Visit funnel runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    qualify = sub.add_parser("qualify")
    qualify.add_argument("--lead-id", required=True)
    qualify.add_argument("--budget", default="")
    qualify.add_argument("--financing-status", default="")
    qualify.add_argument("--timing", default="")
    qualify.add_argument("--motivation", default="")
    qualify.add_argument("--preferred-days", default="")
    qualify.add_argument("--property-price", type=int, default=None)

    propose = sub.add_parser("propose")
    propose.add_argument("--lead-id", required=True)
    propose.add_argument("--days", type=int, default=7)
    propose.add_argument("--event-slug", default="")
    propose.add_argument("--slots-file", default="")

    book = sub.add_parser("book")
    book.add_argument("--lead-id", required=True)
    book.add_argument("--start", required=True)
    book.add_argument("--event-slug", default="")
    book.add_argument("--dry-run", action="store_true")

    reschedule = sub.add_parser("reschedule")
    reschedule.add_argument("--booking-uid", required=True)
    reschedule.add_argument("--start", required=True)
    reschedule.add_argument("--reason", default="")
    reschedule.add_argument("--dry-run", action="store_true")

    cancel = sub.add_parser("cancel")
    cancel.add_argument("--booking-uid", required=True)
    cancel.add_argument("--reason", default="")
    cancel.add_argument("--dry-run", action="store_true")

    briefing = sub.add_parser("briefing")
    briefing.add_argument("--date", default="")

    args = parser.parse_args()

    if args.command == "qualify":
        result = evaluate_qualification(
            {
                "budget": args.budget,
                "financing_status": args.financing_status,
                "timing": args.timing,
                "motivation": args.motivation,
                "preferred_days": args.preferred_days,
            },
            property_price=args.property_price,
        )
        update_lead(
            args.lead_id,
            status=result["status"],
            qualification_rating=result["qualification_rating"],
            budget=result["budget"],
            financing_status=result["financing_status"],
            preferred_days=result["preferred_days"],
            qualified_at=now_iso() if result["status"] == "qualified" else None,
        )
    elif args.command == "propose":
        result = propose_slots(
            lead_id=args.lead_id,
            days=args.days,
            event_slug=args.event_slug,
            slots_file=args.slots_file,
        )
    elif args.command == "book":
        result = book_visit(
            lead_id=args.lead_id,
            start=args.start,
            event_slug=args.event_slug,
            dry_run=args.dry_run,
        )
    elif args.command == "reschedule":
        result = reschedule_visit(
            booking_uid=args.booking_uid,
            start=args.start,
            reason=args.reason,
            dry_run=args.dry_run,
        )
    elif args.command == "cancel":
        result = cancel_visit(
            booking_uid=args.booking_uid,
            reason=args.reason,
            dry_run=args.dry_run,
        )
    else:
        result = build_briefings(target_date=args.date)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
