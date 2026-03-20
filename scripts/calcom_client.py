#!/usr/bin/env python3
"""Small Cal.com v2 client for the managed service setup."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from user_config import load_user_config


class CalcomClient:
    def __init__(self) -> None:
        cfg = load_user_config()
        self.api_key = cfg.calcom_api_key
        self.base_url = cfg.calcom_base_url.rstrip("/")
        self.api_version = cfg.calcom_api_version
        self.username = cfg.calcom_username

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        require_auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})}"

        headers = {
            "Accept": "application/json",
            "cal-api-version": self.api_version,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if require_auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, headers=headers, method=method.upper(), data=data)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Cal.com HTTP {exc.code}: {raw}") from exc

    def get_slots(self, *, event_slug: str, start_time: str, end_time: str, username: str = "") -> dict[str, Any]:
        return self._request(
            "GET",
            "/slots",
            query={
                "username": username or self.username,
                "eventSlug": event_slug,
                "startTime": start_time,
                "endTime": end_time,
            },
            require_auth=False,
        )

    def get_event_types(self, *, username: str = "") -> dict[str, Any]:
        return self._request(
            "GET",
            "/event-types",
            query={"username": username or self.username},
            require_auth=True,
        )

    def create_booking(
        self,
        *,
        event_type_slug: str,
        start: str,
        attendee_name: str,
        attendee_email: str,
        attendee_timezone: str = "Europe/Brussels",
        username: str = "",
        booking_fields_responses: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eventTypeSlug": event_type_slug,
            "username": username or self.username,
            "start": start,
            "attendee": {
                "name": attendee_name,
                "email": attendee_email,
                "timeZone": attendee_timezone,
            },
        }
        if booking_fields_responses:
            payload["bookingFieldsResponses"] = booking_fields_responses
        return self._request("POST", "/bookings", payload=payload, require_auth=False)

    def reschedule_booking(self, *, booking_uid: str, start: str, reason: str = "") -> dict[str, Any]:
        payload = {"start": start}
        if reason:
            payload["rescheduleReason"] = reason
        return self._request(
            "POST",
            f"/bookings/{booking_uid}/reschedule",
            payload=payload,
            require_auth=bool(self.api_key),
        )

    def cancel_booking(self, *, booking_uid: str, reason: str = "") -> dict[str, Any]:
        payload = {}
        if reason:
            payload["cancellationReason"] = reason
        return self._request(
            "POST",
            f"/bookings/{booking_uid}/cancel",
            payload=payload,
            require_auth=bool(self.api_key),
        )

    def get_webhooks(self) -> dict[str, Any]:
        return self._request("GET", "/webhooks", require_auth=True)

    def create_webhook(
        self,
        *,
        subscriber_url: str,
        secret: str = "",
        triggers: list[str] | None = None,
        active: bool = True,
        payload_template: str = "",
        version: str = "2021-10-20",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "active": active,
            "subscriberUrl": subscriber_url,
            "triggers": triggers or ["BOOKING_CREATED", "BOOKING_RESCHEDULED", "BOOKING_CANCELLED"],
            "version": version,
        }
        if secret:
            payload["secret"] = secret
        if payload_template:
            payload["payloadTemplate"] = payload_template
        return self._request("POST", "/webhooks", payload=payload, require_auth=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cal.com v2 CLI wrapper")
    sub = parser.add_subparsers(dest="command", required=True)

    slots = sub.add_parser("slots")
    slots.add_argument("--event-slug", required=True)
    slots.add_argument("--start-time", required=True)
    slots.add_argument("--end-time", required=True)
    slots.add_argument("--username", default="")

    event_types = sub.add_parser("event-types")
    event_types.add_argument("--username", default="")

    book = sub.add_parser("book")
    book.add_argument("--event-slug", required=True)
    book.add_argument("--start", required=True)
    book.add_argument("--attendee-name", required=True)
    book.add_argument("--attendee-email", required=True)
    book.add_argument("--attendee-timezone", default="Europe/Brussels")
    book.add_argument("--username", default="")
    book.add_argument("--fields-json", default="")

    reschedule = sub.add_parser("reschedule")
    reschedule.add_argument("--booking-uid", required=True)
    reschedule.add_argument("--start", required=True)
    reschedule.add_argument("--reason", default="")

    cancel = sub.add_parser("cancel")
    cancel.add_argument("--booking-uid", required=True)
    cancel.add_argument("--reason", default="")

    webhooks = sub.add_parser("webhooks")

    create_webhook = sub.add_parser("create-webhook")
    create_webhook.add_argument("--subscriber-url", required=True)
    create_webhook.add_argument(
        "--triggers",
        default="BOOKING_CREATED,BOOKING_RESCHEDULED,BOOKING_CANCELLED",
        help="Comma-separated webhook triggers",
    )
    create_webhook.add_argument("--secret", default="")
    create_webhook.add_argument("--payload-template", default="")
    create_webhook.add_argument("--inactive", action="store_true")
    create_webhook.add_argument("--version", default="2021-10-20")

    args = parser.parse_args()
    client = CalcomClient()

    if args.command == "slots":
        result = client.get_slots(
            event_slug=args.event_slug,
            start_time=args.start_time,
            end_time=args.end_time,
            username=args.username,
        )
    elif args.command == "event-types":
        result = client.get_event_types(username=args.username)
    elif args.command == "book":
        fields = json.loads(args.fields_json) if args.fields_json else None
        result = client.create_booking(
            event_type_slug=args.event_slug,
            start=args.start,
            attendee_name=args.attendee_name,
            attendee_email=args.attendee_email,
            attendee_timezone=args.attendee_timezone,
            username=args.username,
            booking_fields_responses=fields,
        )
    elif args.command == "reschedule":
        result = client.reschedule_booking(
            booking_uid=args.booking_uid,
            start=args.start,
            reason=args.reason,
        )
    elif args.command == "webhooks":
        result = client.get_webhooks()
    elif args.command == "create-webhook":
        result = client.create_webhook(
            subscriber_url=args.subscriber_url,
            triggers=[item.strip() for item in args.triggers.split(",") if item.strip()],
            secret=args.secret,
            payload_template=args.payload_template,
            active=not args.inactive,
            version=args.version,
        )
    else:
        result = client.cancel_booking(
            booking_uid=args.booking_uid,
            reason=args.reason,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
