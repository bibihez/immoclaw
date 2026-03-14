#!/usr/bin/env python3
"""Lead processing helpers for sale/rental qualification."""

from __future__ import annotations

from typing import Any

from poll_inbox import detect_listing_type


def build_property_args(listing_type: str, price: float | None, charges: float | None = None) -> dict[str, Any]:
    """Build property arguments from listing type.

    For rental listings, the property `price` stores the monthly rent.
    """
    if listing_type == "rental":
        monthly_rent = price or 0
        return {
            "price": monthly_rent,
            "notes": f"Location - {monthly_rent}€/mois + {charges or 0}€ charges",
        }

    return {
        "price": price,
        "notes": "Vente",
    }


def build_lead_email_template(listing_type: str, language: str = "fr") -> str:
    if listing_type == "rental":
        return f"templates/email-lead-form-rental-{language}.md"
    return f"templates/email-lead-form-{language}.md"


def screen_tenant(data: dict) -> tuple[str, list[str]]:
    """Return (score, red_flags) for rental qualification."""
    red_flags: list[str] = []

    income = float(data.get("monthly_income") or 0)
    rent = float(data.get("monthly_rent") or 0)

    if rent > 0 and income > 0:
        ratio = rent / income
        if ratio > 0.5:
            red_flags.append("rent_over_50pct_income")
        elif ratio > 0.33:
            red_flags.append("rent_over_33pct_income")

    employment = (data.get("employment_type") or "").lower()
    duration = data.get("employment_duration", "")
    if employment == "cdi" and duration in ("1-3 ans", "> 3 ans"):
        employment_signal = "strong"
    elif employment == "cdd" or duration == "< 1 an":
        employment_signal = "weak"
        red_flags.append("unstable_employment")
    else:
        employment_signal = "medium"

    has_guarantor = bool(data.get("has_guarantor"))
    if employment_signal == "weak" and not has_guarantor:
        red_flags.append("no_guarantor_despite_weak_employment")

    notice = data.get("notice_period", "")
    if notice in ("3 mois", "autre"):
        red_flags.append("long_notice_period")

    if data.get("smoker"):
        red_flags.append("smoker_info")
    if data.get("has_pets"):
        red_flags.append("pets_info")

    blocking_flags = [f for f in red_flags if f not in ("smoker_info", "pets_info")]
    if len(blocking_flags) == 0:
        return "green", red_flags
    if len(blocking_flags) <= 1:
        return "orange", red_flags
    return "red", red_flags


def resolve_listing_type(subject: str, body: str, price: int | None) -> str:
    return detect_listing_type(subject, body, price)
