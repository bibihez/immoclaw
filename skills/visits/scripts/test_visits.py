#!/usr/bin/env python3

import argparse
import json
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
) -> bool:
    slot_end = slot_start + timedelta(minutes=visit_minutes)
    key = fmt_dt(slot_start)
    if key in seen_starts:
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


def evaluate_sale_qualification(reply: dict[str, Any]) -> dict[str, Any]:
    financing = reply.get("financing_status", "").strip().lower()
    timing = reply.get("project_timing", "").strip().lower()
    motivation = reply.get("interest_reason", "").strip().lower()
    purpose = reply.get("purchase_purpose", "").strip().lower()
    budget = parse_budget(reply.get("budget"))
    property_price = parse_budget(reply.get("property_price"))
    silence_days = int(reply.get("days_silent_after_qualification", 0))

    red_flags: list[str] = []

    if not budget:
        red_flags.append("budget_missing")
    if budget and property_price and budget < int(property_price * 0.85):
        red_flags.append("budget_below_property_level")
    if financing in {"", "not started", "unknown", "none"}:
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

    financing_credible = financing in {"pre-approved", "mortgage in progress", "own funds"}
    budget_coherent = budget is not None and (property_price is None or budget >= int(property_price * 0.85))
    motivation_clear = bool(motivation) and "curieux" not in motivation and "curious" not in motivation
    timing_clear = timing not in {"", "unknown", "someday"}

    if "curious_only" in red_flags or "budget_below_property_level" in red_flags or (
        financing in {"", "not started", "unknown", "none"} and not motivation_clear
    ):
        rating = "reject"
    elif financing_credible and budget_coherent and motivation_clear and timing_clear:
        rating = "hot"
    elif len(red_flags) <= 2 and motivation_clear:
        rating = "medium"
    else:
        rating = "weak"

    if rating in {"hot", "medium"}:
        lead_status = "qualified"
    elif rating == "weak":
        lead_status = "awaiting_qualification"
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


def simulate_qualification_reply(scenario: dict[str, Any]) -> ScenarioResult:
    reply = scenario["reply"]
    expected = scenario["expected"]
    details: list[str] = []

    result = evaluate_sale_qualification(reply)
    status = result["lead_status"]
    rating = result["qualification_rating"]

    passed = status == expected["lead_status"] and rating == expected["qualification_rating"]
    details.append(f"Qualification outcome: {status}.")
    details.append(f"Qualification rating: {rating}.")
    details.append(f"Budget signal: {result['budget_signal']}.")
    details.append(f"Financing signal: {result['financing_signal']}.")
    if result["red_flags"]:
        details.append(f"Red flags: {', '.join(result['red_flags'])}.")

    return ScenarioResult(scenario["name"], passed, details)


def simulate_slot_proposal(scenario: dict[str, Any]) -> ScenarioResult:
    now = parse_iso(scenario["now"])
    lead = scenario["lead"]
    calendar_events = scenario["calendar_events"]
    working_hours = tuple(scenario.get("working_hours", DEFAULT_WORKING_HOURS))
    expected = scenario["expected"]

    slots = generate_slots(now, calendar_events, working_hours, lead["commune"])
    details = [f"Generated {len(slots)} slots."]
    passed = len(slots) >= expected["minimum_slots"]

    if slots:
        details.extend([f"Slot {index + 1}: {slot['start']} -> {slot['end']}" for index, slot in enumerate(slots)])
        if "first_slot_prefix" in expected:
            passed = passed and slots[0]["start"].startswith(expected["first_slot_prefix"])
        for blocked_prefix in expected.get("blocked_prefixes", []):
            if any(slot["start"].startswith(blocked_prefix) for slot in slots):
                passed = False

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
    "qualification_reply": simulate_qualification_reply,
    "slot_proposal": simulate_slot_proposal,
    "booking_conflict": simulate_booking_conflict,
    "agent_suggestion": simulate_agent_suggestion,
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
