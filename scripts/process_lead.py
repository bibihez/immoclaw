#!/usr/bin/env python3
"""Create a lead and send the qualification form email."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from comms_outbound import send_email
from db import create_lead, create_or_get_property, log_email, now_iso, update_lead
from template_render import render_template
from user_config import load_user_config


TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
EMAIL_LANG = os.getenv("EMAIL_LANG", "fr").lower().strip() or "fr"


def build_form_url(*, lead_id: str) -> str:
    cfg = load_user_config()
    template = cfg.form_fr_prefill_url_template if EMAIL_LANG == "fr" else cfg.form_nl_prefill_url_template
    if not template:
        raise RuntimeError("Missing qualification form URL template in USER.md or environment")
    return template.replace("{lead_id}", lead_id)


def send_form_email(
    *,
    lead_id: str,
    lead_name: str,
    lead_email: str,
    property_address: str,
) -> dict[str, object]:
    cfg = load_user_config()
    if not cfg.agentmail_inbox_id:
        return {"success": False, "error": "Missing AgentMail inbox id"}

    lang = EMAIL_LANG if EMAIL_LANG in {"fr", "nl"} else "fr"
    template_path = Path(__file__).resolve().parents[1] / "templates" / f"email-lead-form-{lang}.md"
    signature = cfg.signature_fr if lang == "fr" else cfg.signature_nl
    if not signature:
        signature = cfg.signature_fr

    form_url = build_form_url(lead_id=lead_id)
    body = render_template(
        template_path,
        lead_name=lead_name,
        adresse=property_address,
        form_url=form_url,
        signature_agent=signature,
    )
    subject_prefix = "[TEST] " if TEST_MODE else ""
    subject = f"{subject_prefix}Votre visite - {property_address}"
    test_email = TEST_EMAIL or cfg.agent_email

    result = send_email(
        inbox_id=cfg.agentmail_inbox_id,
        to_email=lead_email,
        subject=subject,
        text=body,
        test_mode=TEST_MODE,
        test_email=test_email,
        agentmail_api_key=cfg.agentmail_api_key,
    )
    return {
        "success": result.success,
        "sent_to": result.sent_to,
        "error": result.error,
        "raw": result.raw,
        "form_url": form_url,
    }


def process_lead(
    *,
    name: str,
    phone: str = "",
    email: str = "",
    street: str = "",
    postcode: str = "",
    commune: str = "",
    price: int | None = None,
    property_id: str = "",
    property_address: str = "",
) -> dict[str, object]:
    address = property_address or ", ".join(part for part in [street, f"{postcode} {commune}".strip()] if part).strip(", ")
    property_notes = f"Imported from Immoweb lead. Asking price: {price or 'unknown'}"
    property_id = create_or_get_property(
        property_id=property_id,
        address=address or "Unknown address",
        commune=commune,
        postcode=postcode,
        notes=property_notes,
    )
    notes = f"Immoweb lead for {address or 'unknown address'}"
    lead_id = create_lead(
        property_id=property_id,
        name=name,
        phone=phone,
        email=email,
        source="immoweb",
        language=EMAIL_LANG,
        budget=price,
        notes=notes,
    )

    email_result: dict[str, object] | None = None
    if email:
        email_result = send_form_email(
            lead_id=lead_id,
            lead_name=name,
            lead_email=email,
            property_address=address or "Adresse à confirmer",
        )
        if email_result.get("success"):
            update_lead(lead_id, status="form_sent", form_sent_at=now_iso())
            log_email(
                lead_id=lead_id,
                property_id=property_id,
                direction="outbound",
                recipient=str(email_result.get("sent_to", "")),
                subject=f"Votre visite - {address}",
                status="sent",
            )
        else:
            log_email(
                lead_id=lead_id,
                property_id=property_id,
                direction="outbound",
                recipient=email,
                subject=f"Votre visite - {address}",
                status="failed",
            )

    return {
        "lead_id": lead_id,
        "property_id": property_id,
        "address": address,
        "email_lang": EMAIL_LANG,
        "email_sent": bool(email_result and email_result.get("success")),
        "email_result": email_result,
        "test_mode": TEST_MODE,
        "next_step": "Wait for qualification, then propose curated Cal.com slots.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Process an incoming Immoweb lead")
    parser.add_argument("--name", required=True)
    parser.add_argument("--phone", default="")
    parser.add_argument("--email", default="")
    parser.add_argument("--street", default="")
    parser.add_argument("--postcode", default="")
    parser.add_argument("--commune", default="")
    parser.add_argument("--price", type=int, default=None)
    parser.add_argument("--property-id", default="")
    parser.add_argument("--property-address", default="")
    args = parser.parse_args()
    result = process_lead(
        name=args.name,
        phone=args.phone,
        email=args.email,
        street=args.street,
        postcode=args.postcode,
        commune=args.commune,
        price=args.price,
        property_id=args.property_id,
        property_address=args.property_address,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
