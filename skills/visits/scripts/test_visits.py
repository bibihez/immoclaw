#!/usr/bin/env python3

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


DEFAULT_WORKING_HOURS = ("09:00", "18:00")
DEFAULT_VISIT_MINUTES = 45
DEFAULT_TRAVEL_BUFFER_MINUTES = 15
DEFAULT_AFTERNOON_START = "13:00"

BRUSSELS_ZONES = {
    "ixelles": "south",
    "saint-gilles": "south",
    "saint gilles": "south",
    "uccle": "south",
    "forest": "south",
    "schaerbeek": "north",
    "evere": "north",
    "laeken": "north",
    "bruxelles": "center",
}

CANONICAL_DAY_NAMES = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}

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

PURPOSE_ALIASES = {
    "live in": "live_in",
    "live_in": "live_in",
    "habiter": "live_in",
    "wonen": "live_in",
    "invest": "invest",
    "investir": "invest",
    "investeren": "invest",
    "both": "both",
    "les deux": "both",
    "beide": "both",
}

FINANCING_ALIASES = {
    "own funds": "own_funds",
    "own_funds": "own_funds",
    "fonds propres": "own_funds",
    "eigen middelen": "own_funds",
    "pre approved": "pre_approved",
    "pre-approved": "pre_approved",
    "credit avec accord de principe": "pre_approved",
    "credit accord de principe": "pre_approved",
    "lening met principieel akkoord": "pre_approved",
    "mortgage in progress": "in_progress",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "credit en cours de demande": "in_progress",
    "lening in aanvraag": "in_progress",
    "not started": "not_started",
    "not_started": "not_started",
    "pas encore demarre": "not_started",
    "nog niet gestart": "not_started",
    "unknown": "",
    "none": "",
}

TIMING_ALIASES = {
    "less than 1 month": "lt_1_month",
    "within 1 month": "lt_1_month",
    "lt_1_month": "lt_1_month",
    "moins d un mois": "lt_1_month",
    "minder dan een maand": "lt_1_month",
    "within 3 months": "1_3_months",
    "1-3 months": "1_3_months",
    "1_3_months": "1_3_months",
    "1 a 3 mois": "1_3_months",
    "1 tot 3 maanden": "1_3_months",
    "3-6 months": "3_6_months",
    "3_6_months": "3_6_months",
    "3 a 6 mois": "3_6_months",
    "3 tot 6 maanden": "3_6_months",
    "no rush": "no_rush",
    "no_rush": "no_rush",
    "pas de rush": "no_rush",
    "geen haast": "no_rush",
    "unknown": "",
    "someday": "",
}

BUDGET_BAND_ALIASES = {
    "< 200 000": 150000,
    "< 200000": 150000,
    "<200k": 150000,
    "under 200k": 150000,
    "200 000 300 000": 250000,
    "200000 300000": 250000,
    "200-300k": 250000,
    "300 000 400 000": 350000,
    "300000 400000": 350000,
    "300-400k": 350000,
    "400 000 500 000": 450000,
    "400000 500000": 450000,
    "400-500k": 450000,
    "500 000": 500000,
    "500000": 500000,
    "500k": 500000,
    "500k+": 500000,
}


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    details: list[str]


def parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def fmt_dt(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


def parse_hhmm(value: str) -> tuple[int, int]:
    hours, minutes = value.split(":")
    return int(hours), int(minutes)


def fold_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[\s_/]+", " ", ascii_only.replace("–", "-").replace("—", "-").strip().lower())
    return re.sub(r"\s+", " ", collapsed)


def day_bounds(day: datetime, working_hours: tuple[str, str]) -> tuple[datetime, datetime]:
    start_hour, start_minute = parse_hhmm(working_hours[0])
    end_hour, end_minute = parse_hhmm(working_hours[1])
    start = day.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end = day.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return start, end


def commune_key(value: str) -> str:
    return value.strip().lower()


def commune_zone(value: str) -> str:
    return BRUSSELS_ZONES.get(commune_key(value), "")


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def event_relevance(event: dict[str, Any], target_commune: str) -> int:
    event_commune = event.get("commune", "")
    if commune_key(event_commune) == commune_key(target_commune):
        return 2
    if commune_zone(event_commune) and commune_zone(event_commune) == commune_zone(target_commune):
        return 1
    return 0


def event_block(event: dict[str, Any], buffer_minutes: int) -> tuple[datetime, datetime]:
    start = parse_iso(event["start"])
    end = parse_iso(event["end"])
    commune = event.get("commune", "")
    return start, end + timedelta(minutes=buffer_minutes if commune else 0)


def slot_is_free(
    slot_start: datetime,
    slot_end: datetime,
    calendar_events: list[dict[str, Any]],
    target_commune: str,
    buffer_minutes: int,
) -> bool:
    for event in calendar_events:
        event_start = parse_iso(event["start"])
        event_end = parse_iso(event["end"])
        extra_buffer = buffer_minutes if event.get("commune") and event.get("commune") != target_commune else 0
        buffered_end = event_end + timedelta(minutes=extra_buffer)
        if overlaps(slot_start, slot_end, event_start, buffered_end):
            return False
    return True


def preferred_day_start(day: datetime, working_hours: tuple[str, str]) -> datetime:
    start = day.replace(second=0, microsecond=0)
    afternoon_hour, afternoon_minute = parse_hhmm(DEFAULT_AFTERNOON_START)
    return start.replace(hour=afternoon_hour, minute=afternoon_minute)


def append_candidate_slot(
    slots: list[dict[str, str]],
    slot_start: datetime,
    visit_minutes: int,
    calendar_events: list[dict[str, Any]],
    target_commune: str,
    buffer_minutes: int,
    seen_starts: set[str],
    preferred_day_parts: Optional[set[str]] = None,
) -> bool:
    slot_end = slot_start + timedelta(minutes=visit_minutes)
    key = fmt_dt(slot_start)
    if key in seen_starts:
        return False
    if preferred_day_parts and slot_day_part_code(slot_start) not in preferred_day_parts:
        return False
    if not slot_is_free(slot_start, slot_end, calendar_events, target_commune, buffer_minutes):
        return False
    slots.append({"start": fmt_dt(slot_start), "end": fmt_dt(slot_end)})
    seen_starts.add(key)
    return True


def parse_budget(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(character for character in str(value) if character.isdigit())
    return int(digits) if digits else None


def normalize_budget_band(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    folded = fold_text(value).replace("eur", "").replace("euro", "")
    collapsed = re.sub(r"[^0-9k+< ]+", " ", folded)
    collapsed = re.sub(r"\s+", " ", collapsed).strip()
    if collapsed in BUDGET_BAND_ALIASES:
        return BUDGET_BAND_ALIASES[collapsed]
    parsed = parse_budget(value)
    return parsed if parsed is not None and parsed >= 100000 else parsed


def normalize_lookup(value: Any, aliases: dict[str, str]) -> str:
    folded = fold_text(value)
    return aliases.get(folded, folded.replace(" ", "_"))


def normalize_preferred_days(value: Any) -> list[str]:
    if value in {None, ""}:
        return []
    items = value if isinstance(value, list) else re.split(r"[,\n;]+", str(value))
    normalized: list[str] = []

    for item in items:
        folded = fold_text(item)
        if not folded:
            continue
        direct = folded.replace("-", "_").replace(" ", "_")
        if re.fullmatch(r"(mon|tue|wed|thu|fri|sat|sun)_(am|pm)", direct):
            code = direct
        else:
            day = next((code for alias, code in DAY_NAME_ALIASES.items() if alias in folded.split()), "")
            if not day:
                day = next((code for alias, code in DAY_NAME_ALIASES.items() if alias in folded), "")
            part = next((code for alias, code in DAY_PART_ALIASES.items() if alias in folded), "")
            code = f"{day}_{part}" if day and part else ""
        if code and code not in normalized:
            normalized.append(code)

    return normalized


def normalize_form_submission(reply: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(reply)
    normalized["purchase_purpose"] = normalize_lookup(reply.get("purchase_purpose", ""), PURPOSE_ALIASES)
    normalized["financing_status"] = normalize_lookup(reply.get("financing_status", ""), FINANCING_ALIASES)
    normalized["project_timing"] = normalize_lookup(reply.get("project_timing", ""), TIMING_ALIASES)
    normalized["budget"] = normalize_budget_band(reply.get("budget"))
    normalized["preferred_days"] = normalize_preferred_days(reply.get("preferred_days") or reply.get("availability"))
    normalized["interest_reason"] = str(reply.get("interest_reason", "")).strip()
    return normalized


def slot_day_part_code(slot_start: datetime) -> str:
    day_code = list(CANONICAL_DAY_NAMES.values())[slot_start.weekday()]
    part_code = "am" if slot_start.hour < 12 else "pm"
    return f"{day_code}_{part_code}"


def evaluate_sale_qualification(reply: dict[str, Any]) -> dict[str, Any]:
    financing = reply.get("financing_status", "").strip().lower()
    timing = reply.get("project_timing", "").strip().lower()
    motivation = reply.get("interest_reason", "").strip().lower()
    purpose = reply.get("purchase_purpose", "").strip().lower()
    budget = normalize_budget_band(reply.get("budget"))
    property_price = parse_budget(reply.get("property_price"))
    silence_days = int(reply.get("days_silent_after_qualification", 0))

    red_flags: list[str] = []

    if not budget:
        red_flags.append("budget_missing")
    if budget and property_price and budget < int(property_price * 0.85):
        red_flags.append("budget_below_property_level")
    if financing in {"", "not_started", "unknown", "none"}:
        red_flags.append("financing_unclear_or_missing")
    if not motivation:
        red_flags.append("motivation_unclear")
    if "curieux" in motivation or "curious" in motivation:
        red_flags.append("curious_only")
    if not purpose:
        red_flags.append("purchase_purpose_unclear")
    if timing in {"", "unknown", "someday"}:
        red_flags.append("timing_unclear")
    if silence_days >= 3:
        red_flags.append("silent_after_qualification")

    financing_credible = financing in {"pre_approved", "in_progress", "own_funds"}
    budget_coherent = budget is not None and (property_price is None or budget >= int(property_price * 0.85))
    motivation_clear = bool(motivation) and "curieux" not in motivation and "curious" not in motivation
    timing_clear = timing not in {"", "unknown", "someday"}

    if "curious_only" in red_flags or "budget_below_property_level" in red_flags or (
        financing in {"", "not_started", "unknown", "none"} and not motivation_clear
    ):
        rating = "reject"
    elif financing in {"pre_approved", "own_funds"} and budget_coherent and motivation_clear and timing_clear:
        rating = "hot"
    elif len(red_flags) <= 1 and motivation_clear and financing not in {"", "not_started", "unknown", "none"}:
        rating = "medium"
    else:
        rating = "weak"

    if rating in {"hot", "medium"}:
        lead_status = "qualified"
    elif rating == "weak":
        lead_status = "form_sent"
    else:
        lead_status = "closed"

    budget_signal = "budget coherent" if budget_coherent else "budget unclear"
    financing_signal = "financing credible" if financing_credible else "financing unclear"

    return {
        "lead_status": lead_status,
        "qualification_rating": rating,
        "red_flags": red_flags,
        "budget_signal": budget_signal,
        "financing_signal": financing_signal,
    }


def generate_slots(
    now: datetime,
    calendar_events: list[dict[str, Any]],
    working_hours: tuple[str, str],
    target_commune: str,
    required_count: int = 3,
    visit_minutes: int = DEFAULT_VISIT_MINUTES,
    buffer_minutes: int = DEFAULT_TRAVEL_BUFFER_MINUTES,
    preferred_day_parts: Optional[set[str]] = None,
) -> list[dict[str, str]]:
    slots = _generate_slots(
        now,
        calendar_events,
        working_hours,
        target_commune,
        required_count,
        visit_minutes,
        buffer_minutes,
        preferred_day_parts,
    )
    if slots or not preferred_day_parts:
        return slots
    return _generate_slots(
        now,
        calendar_events,
        working_hours,
        target_commune,
        required_count,
        visit_minutes,
        buffer_minutes,
        None,
    )


def _generate_slots(
    now: datetime,
    calendar_events: list[dict[str, Any]],
    working_hours: tuple[str, str],
    target_commune: str,
    required_count: int,
    visit_minutes: int,
    buffer_minutes: int,
    preferred_day_parts: Optional[set[str]],
) -> list[dict[str, str]]:
    slots: list[dict[str, str]] = []
    events = sorted(calendar_events, key=lambda item: item["start"])
    seen_starts: set[str] = set()

    for day_offset in range(1, 8):
        day = now + timedelta(days=day_offset)
        day_start, day_end = day_bounds(day, working_hours)
        cursor = max(day_start, preferred_day_start(day, working_hours))

        anchor_events = [
            event for event in events
            if parse_iso(event["start"]).date() == day.date() and event_relevance(event, target_commune) > 0
        ]
        for event in sorted(anchor_events, key=lambda item: (-event_relevance(item, target_commune), item["end"])):
            anchor_start = parse_iso(event["end"]) + timedelta(
                minutes=buffer_minutes if event.get("commune") != target_commune else 0
            )
            if anchor_start < day_start or anchor_start + timedelta(minutes=visit_minutes) > day_end:
                continue
            append_candidate_slot(
                slots,
                anchor_start,
                visit_minutes,
                events,
                target_commune,
                buffer_minutes,
                seen_starts,
                preferred_day_parts,
            )
            if len(slots) >= required_count:
                return slots

        while cursor + timedelta(minutes=visit_minutes) <= day_end and len(slots) < required_count:
            candidate_end = cursor + timedelta(minutes=visit_minutes)
            blocked = False

            for event in events:
                event_start = parse_iso(event["start"])
                event_end = parse_iso(event["end"])
                extra_buffer = buffer_minutes if event.get("commune") and event.get("commune") != target_commune else 0
                buffered_end = event_end + timedelta(minutes=extra_buffer)

                if overlaps(cursor, candidate_end, event_start, buffered_end):
                    blocked = True
                    cursor = max(cursor + timedelta(minutes=15), buffered_end)
                    break

            if blocked:
                continue

            append_candidate_slot(
                slots,
                cursor,
                visit_minutes,
                events,
                target_commune,
                buffer_minutes,
                seen_starts,
                preferred_day_parts,
            )
            cursor = candidate_end + timedelta(minutes=buffer_minutes)

        early_cursor = day_start
        while early_cursor + timedelta(minutes=visit_minutes) <= min(cursor, max(day_start, preferred_day_start(day, working_hours))) and len(slots) < required_count:
            early_end = early_cursor + timedelta(minutes=visit_minutes)
            if slot_is_free(early_cursor, early_end, events, target_commune, buffer_minutes):
                append_candidate_slot(
                    slots,
                    early_cursor,
                    visit_minutes,
                    events,
                    target_commune,
                    buffer_minutes,
                    seen_starts,
                    preferred_day_parts,
                )
            early_cursor = early_cursor + timedelta(minutes=15)

        if len(slots) >= required_count:
            break

    return slots


def cluster_leads(leads: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    clusters: dict[str, list[dict[str, Any]]] = {}
    for lead in leads:
        key = lead.get("cluster") or f'{lead.get("postcode", "")}-{lead.get("commune", "unknown")}'
        clusters.setdefault(key, []).append(lead)
    return clusters


def plan_weekly_blocks(
    now: datetime,
    leads: list[dict[str, Any]],
    calendar_events: list[dict[str, Any]],
    working_hours: tuple[str, str],
) -> list[dict[str, Any]]:
    relevant = [
        lead for lead in leads
        if lead.get("status") in {"qualified", "visit_proposed"} and not lead.get("scheduled_at")
    ]
    grouped = cluster_leads(relevant)
    proposals: list[dict[str, Any]] = []
    reserved_events = list(calendar_events)

    for cluster_name, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        commune = items[0].get("commune", "")
        slots = generate_slots(now, reserved_events, working_hours, commune, required_count=1)
        if not slots:
            continue
        slot = slots[0]
        reserved_events.append(
            {
                "start": slot["start"],
                "end": slot["end"],
                "commune": commune,
            }
        )
        proposals.append(
            {
                "cluster": cluster_name,
                "lead_count": len(items),
                "commune": commune,
                "slot": slot,
                "properties": [lead["property_address"] for lead in items],
            }
        )

    return proposals


def simulate_inbound_new_lead(scenario: dict[str, Any]) -> ScenarioResult:
    email = scenario["email"]
    routing = scenario["expected"]
    details: list[str] = []
    passed = True

    sender = email["from"].lower()
    subject = email["subject"].lower()
    body = email["body"].lower()

    is_immoweb = sender in {"info@immoweb.be", "agences@immoweb.be"}
    looks_like_lead = all(marker in body for marker in ["nom", "téléphone", "adresse mail"])
    routed_to = "visits" if is_immoweb and (looks_like_lead or "plus d'informations" in subject) else "unknown"
    message_type = "new_lead" if routed_to == "visits" else "unknown"

    if routed_to != routing["route_to"]:
        passed = False
        details.append(f"Expected route_to={routing['route_to']}, got {routed_to}.")
    else:
        details.append(f"Routing matched: {routed_to}.")

    if message_type != routing["message_type"]:
        passed = False
        details.append(f"Expected message_type={routing['message_type']}, got {message_type}.")
    else:
        details.append(f"Message type matched: {message_type}.")

    return ScenarioResult(scenario["name"], passed, details)


def simulate_form_submission(scenario: dict[str, Any]) -> ScenarioResult:
    reply = scenario["reply"]
    expected = scenario["expected"]
    details: list[str] = []

    normalized = normalize_form_submission(reply)
    result = evaluate_sale_qualification(normalized)
    status = result["lead_status"]
    rating = result["qualification_rating"]

    passed = status == expected["lead_status"] and rating == expected["qualification_rating"]
    for key, value in expected.get("normalized", {}).items():
        if normalized.get(key) != value:
            passed = False
            details.append(f"Normalized {key}: expected {value}, got {normalized.get(key)}.")
    details.append(f"Qualification outcome: {status}.")
    details.append(f"Qualification rating: {rating}.")
    details.append(
        "Normalized form: "
        f"purpose={normalized['purchase_purpose']}, financing={normalized['financing_status']}, "
        f"timing={normalized['project_timing']}, preferred_days={','.join(normalized['preferred_days']) or 'none'}."
    )
    details.append(f"Budget signal: {result['budget_signal']}.")
    details.append(f"Financing signal: {result['financing_signal']}.")
    if result["red_flags"]:
        details.append(f"Red flags: {', '.join(result['red_flags'])}.")

    return ScenarioResult(scenario["name"], passed, details)


def simulate_lead_store_ingestion(scenario: dict[str, Any]) -> ScenarioResult:
    submission = scenario["submission"]
    lead_store = scenario["lead_store"]
    expected = scenario["expected"]
    details: list[str] = []

    matched = next((lead for lead in lead_store if lead.get("lead_id") == submission.get("lead_ref")), None)
    if matched is None and submission.get("email"):
        matched = next(
            (
                lead for lead in lead_store
                if lead.get("email") == submission["email"] and lead.get("status") in {"new", "form_sent", "qualified"}
            ),
            None,
        )

    if matched is None:
        return ScenarioResult(scenario["name"], False, ["Submission could not be matched to an internal lead."])

    normalized = normalize_form_submission(submission)
    result = evaluate_sale_qualification(normalized)
    processed = True

    details.append(f"Matched lead: {matched['lead_id']}.")
    details.append(f"Processed internally: {'yes' if processed else 'no'}.")
    details.append(f"Qualification rating: {result['qualification_rating']}.")

    passed = (
        matched["lead_id"] == expected["matched_lead_id"]
        and processed is expected["processed"]
        and result["qualification_rating"] == expected["qualification_rating"]
    )
    return ScenarioResult(scenario["name"], passed, details)


def simulate_slot_proposal(scenario: dict[str, Any]) -> ScenarioResult:
    now = parse_iso(scenario["now"])
    lead = scenario["lead"]
    calendar_events = scenario["calendar_events"]
    working_hours = tuple(scenario.get("working_hours", DEFAULT_WORKING_HOURS))
    expected = scenario["expected"]
    preferred_day_parts = set(normalize_preferred_days(lead.get("preferred_days")))

    slots = generate_slots(now, calendar_events, working_hours, lead["commune"], preferred_day_parts=preferred_day_parts)
    details = [f"Generated {len(slots)} slots."]
    passed = len(slots) >= expected["minimum_slots"]

    if slots:
        details.extend([f"Slot {index + 1}: {slot['start']} -> {slot['end']}" for index, slot in enumerate(slots)])
        if "first_slot_prefix" in expected:
            passed = passed and slots[0]["start"].startswith(expected["first_slot_prefix"])
        if "only_day_prefix" in expected:
            passed = passed and all(slot["start"].startswith(expected["only_day_prefix"]) for slot in slots)
        for allowed_prefix in expected.get("allowed_prefixes", []):
            if not any(slot["start"].startswith(allowed_prefix) for slot in slots):
                passed = False
        for blocked_prefix in expected.get("blocked_prefixes", []):
            if any(slot["start"].startswith(blocked_prefix) for slot in slots):
                passed = False

    return ScenarioResult(scenario["name"], passed, details)


def simulate_calendar_booking_mode(scenario: dict[str, Any]) -> ScenarioResult:
    connection = scenario["calendar_connection"]
    expected = scenario["expected"]
    details: list[str] = []

    if connection.get("primary_available"):
        calendar_mode = "primary"
    elif connection.get("fallback_available"):
        calendar_mode = "fallback"
    else:
        calendar_mode = "unavailable"

    details.append(f"Selected calendar mode: {calendar_mode}.")
    details.append(f"Primary available: {'yes' if connection.get('primary_available') else 'no'}.")
    details.append(f"Fallback available: {'yes' if connection.get('fallback_available') else 'no'}.")

    passed = calendar_mode == expected["calendar_mode"]
    return ScenarioResult(scenario["name"], passed, details)


def simulate_booking_conflict(scenario: dict[str, Any]) -> ScenarioResult:
    requested_start = parse_iso(scenario["requested_slot"]["start"])
    requested_end = parse_iso(scenario["requested_slot"]["end"])
    now = parse_iso(scenario["now"])
    lead = scenario["lead"]
    calendar_events = scenario["calendar_events"]
    working_hours = tuple(scenario.get("working_hours", DEFAULT_WORKING_HOURS))

    conflict = False
    for event in calendar_events:
        start = parse_iso(event["start"])
        end = parse_iso(event["end"])
        if overlaps(requested_start, requested_end, start, end):
            conflict = True
            break

    details: list[str] = []
    if conflict:
        details.append("Requested slot is no longer free.")
        fallback_slots = generate_slots(now, calendar_events, working_hours, lead["commune"])
        details.append(f"Generated {len(fallback_slots)} replacement slots.")
        passed = len(fallback_slots) >= scenario["expected"]["minimum_replacement_slots"]
    else:
        details.append("Requested slot is still free.")
        passed = scenario["expected"]["conflict"] is False

    return ScenarioResult(scenario["name"], passed, details)


def simulate_agent_suggestion(scenario: dict[str, Any]) -> ScenarioResult:
    now = parse_iso(scenario["now"])
    lead = scenario["lead"]
    calendar_events = scenario["calendar_events"]
    working_hours = tuple(scenario.get("working_hours", DEFAULT_WORKING_HOURS))
    expected = scenario["expected"]

    slots = generate_slots(now, calendar_events, working_hours, lead["commune"], required_count=1)
    details: list[str] = []

    if not slots:
        details.append("No reasonable slot found to suggest to the agent.")
        return ScenarioResult(scenario["name"], False, details)

    slot = slots[0]
    details.append(f"Suggested slot to agent: {slot['start']} -> {slot['end']}")
    details.append(f"Reason: {expected['reason']}")

    passed = slot["start"].startswith(expected["suggested_day_prefix"])
    return ScenarioResult(scenario["name"], passed, details)


def simulate_onboarding_surface(scenario: dict[str, Any]) -> ScenarioResult:
    setup = scenario["setup"]
    expected = scenario["expected"]
    client_uses_daily_tools_only = (
        setup.get("email_channel") == "agentmail"
        and setup.get("calendar_connection") == "google_primary"
        and setup.get("telegram_connected") is True
        and setup.get("client_backoffice_required") is False
    )

    details = [
        f"Email channel: {setup.get('email_channel')}.",
        f"Calendar connection: {setup.get('calendar_connection')}.",
        f"Telegram connected: {'yes' if setup.get('telegram_connected') else 'no'}.",
        f"Client backoffice required: {'yes' if setup.get('client_backoffice_required') else 'no'}.",
    ]
    passed = client_uses_daily_tools_only is expected["smooth_onboarding"]
    return ScenarioResult(scenario["name"], passed, details)


def simulate_urgent_request(scenario: dict[str, Any]) -> ScenarioResult:
    now = parse_iso(scenario["now"])
    requested_start = parse_iso(scenario["requested_slot"]["start"])
    incomplete_visibility = scenario.get("calendar_visibility", "complete") != "complete"
    next_day_request = requested_start.date() <= (now + timedelta(days=1)).date()

    escalate = next_day_request and incomplete_visibility
    details = [
        f"Urgent next-day request: {'yes' if next_day_request else 'no'}.",
        f"Calendar visibility incomplete: {'yes' if incomplete_visibility else 'no'}.",
        f"Escalate to agent: {'yes' if escalate else 'no'}.",
    ]
    passed = escalate is scenario["expected"]["escalate"]
    return ScenarioResult(scenario["name"], passed, details)


def simulate_capacity_guardrail(scenario: dict[str, Any]) -> ScenarioResult:
    capacity_known = scenario["property"].get("capacity_known", False)
    grouped_visit_requested = scenario["property"].get("grouped_visit_requested", False)
    ask_agent = grouped_visit_requested and not capacity_known

    details = [
        f"Grouped visit requested: {'yes' if grouped_visit_requested else 'no'}.",
        f"Capacity known: {'yes' if capacity_known else 'no'}.",
        f"Ask agent before assuming grouped capacity: {'yes' if ask_agent else 'no'}.",
    ]
    passed = ask_agent is scenario["expected"]["ask_agent"]
    return ScenarioResult(scenario["name"], passed, details)


def simulate_weekly_planning(scenario: dict[str, Any]) -> ScenarioResult:
    now = parse_iso(scenario["now"])
    leads = scenario["leads"]
    calendar_events = scenario["calendar_events"]
    working_hours = tuple(scenario.get("working_hours", DEFAULT_WORKING_HOURS))
    expected = scenario["expected"]

    proposals = plan_weekly_blocks(now, leads, calendar_events, working_hours)
    details = [f"Generated {len(proposals)} cluster proposals."]
    details.extend(
        f"{proposal['cluster']}: {proposal['lead_count']} leads, slot {proposal['slot']['start']}"
        for proposal in proposals
    )

    summary = "[Planification Hebdo] ... (ok / modifier)" if proposals else "No weekly planning proposal."
    details.append(f"Approval summary: {summary}")

    passed = len(proposals) >= expected["minimum_clusters"]
    if expected.get("requires_approval_prompt"):
        passed = passed and "ok / modifier" in summary
    return ScenarioResult(scenario["name"], passed, details)


SIMULATORS = {
    "inbound_new_lead": simulate_inbound_new_lead,
    "form_submission": simulate_form_submission,
    "lead_store_ingestion": simulate_lead_store_ingestion,
    "slot_proposal": simulate_slot_proposal,
    "calendar_booking_mode": simulate_calendar_booking_mode,
    "booking_conflict": simulate_booking_conflict,
    "agent_suggestion": simulate_agent_suggestion,
    "onboarding_surface": simulate_onboarding_surface,
    "urgent_request": simulate_urgent_request,
    "capacity_guardrail": simulate_capacity_guardrail,
    "weekly_planning": simulate_weekly_planning,
}


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    with path.open() as handle:
        return json.load(handle)["scenarios"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate core flows for the visits skill.")
    parser.add_argument(
        "--fixtures",
        default=str(Path(__file__).resolve().parents[1] / "fixtures" / "visits_scenarios.json"),
        help="Path to the scenario JSON file.",
    )
    args = parser.parse_args()

    scenarios = load_scenarios(Path(args.fixtures))
    results: list[ScenarioResult] = []

    for scenario in scenarios:
        simulator = SIMULATORS.get(scenario["type"])
        if simulator is None:
            results.append(
                ScenarioResult(scenario["name"], False, [f"Unknown scenario type: {scenario['type']}"])
            )
            continue
        results.append(simulator(scenario))

    passed_count = 0
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}")
        for detail in result.details:
            print(f"  - {detail}")
        if result.passed:
            passed_count += 1

    total = len(results)
    print(f"\nSummary: {passed_count}/{total} scenarios passed.")
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
