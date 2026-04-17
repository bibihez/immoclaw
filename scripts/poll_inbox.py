#!/usr/bin/env python3
"""Inbox classification helpers for Immoclaw."""

from __future__ import annotations

import json
import re
from typing import Any


def _extract_price_eur(text: str) -> int | None:
    matches = re.findall(r"([\d\s\.]{3,})\s*€", text)
    prices: list[int] = []
    for match in matches:
        digits = re.sub(r"\D", "", match)
        if digits:
            prices.append(int(digits))
    return max(prices) if prices else None


def _search_number(pattern: str, body: str, flags: int = re.IGNORECASE) -> int | None:
    match = re.search(pattern, body, flags)
    if not match:
        return None
    return int(match.group(1))


def detect_listing_type(subject: str, body: str, price: int | None = None) -> str:
    """Detect if the listing is sale or rental."""
    combined = f"{subject} {body}".lower()

    if any(w in combined for w in ["à louer", "a louer", "location", "loyer", "te huur", "huur"]):
        return "rental"
    if any(w in combined for w in ["à vendre", "a vendre", "vente", "te koop", "koop"]):
        return "sale"

    if price:
        if price < 5000:
            return "rental"
        if price > 50000:
            return "sale"

    return "unknown"


def classify_email(subject: str, body: str) -> dict[str, Any]:
    """Classify Immoweb lead and return normalized payload."""
    price = _extract_price_eur(body) or _extract_price_eur(subject)
    listing_type = detect_listing_type(subject, body, price)

    charges_match = re.search(r"Charges?\s*[:\uff1a]\s*([\d\s\.]+)\s*€", body, re.IGNORECASE)
    charges = int(re.sub(r"\D", "", charges_match.group(1))) if charges_match else None
    furnished = bool(re.search(r"(meublé|gemeubileerd|furnished)", body, re.IGNORECASE))
    surface = _search_number(r"([\d]+)\s*m[²2]", body)
    rooms = _search_number(r"([\d]+)\s*(?:ch|chambres|kamers)", body)

    name_match = re.search(r"Nom\s*[:\uff1a]\s*([^\n]+)", body, re.IGNORECASE)
    phone_match = re.search(r"(?:Téléphone|Tel|GSM)\s*[:\uff1a]\s*([^\n]+)", body, re.IGNORECASE)
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", body, re.IGNORECASE)

    return {
        "skill": "visits",
        "message_type": "new_lead",
        "listing_type": listing_type,
        "lead_data": {
            "name": name_match.group(1).strip() if name_match else None,
            "phone": phone_match.group(1).strip() if phone_match else None,
            "email": email_match.group(0).strip() if email_match else None,
            "price": price,
            "charges": charges,
            "surface": surface,
            "rooms": rooms,
            "furnished": furnished,
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Classify Immoweb email")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    args = parser.parse_args()

    print(json.dumps(classify_email(args.subject, args.body), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
