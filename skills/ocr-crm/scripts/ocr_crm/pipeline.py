from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import OpenAIConfig, RuntimeConfig, ZabunConfig
from .exceptions import ValidationError
from .openai_provider import OpenAIProvider
from .storage import SessionStore
from .utils import (
    best_option_match,
    cleanup_none,
    copy_with_possible_conversion,
    detect_asset_kind,
    dump_json,
    ensure_dir,
    first_non_empty,
    normalize_text,
    split_mobile_cc,
    utcnow_iso,
)
from .zabun_client import ZabunClient


@dataclass
class PipelineDependencies:
    store: SessionStore
    zabun: ZabunClient
    openai: OpenAIProvider
    runtime: RuntimeConfig
    zabun_config: ZabunConfig


class IngestionPipeline:
    def __init__(self, dependencies: PipelineDependencies) -> None:
        self.deps = dependencies

    @classmethod
    def from_env(cls, skill_dir: Path) -> "IngestionPipeline":
        runtime = RuntimeConfig.from_env(skill_dir)
        dependencies = PipelineDependencies(
            store=SessionStore(runtime.state_dir),
            zabun=ZabunClient(ZabunConfig.from_env(), timeout=runtime.request_timeout_seconds),
            openai=OpenAIProvider(OpenAIConfig.from_env(), timeout=runtime.request_timeout_seconds),
            runtime=runtime,
            zabun_config=ZabunConfig.from_env(),
        )
        return cls(dependencies)

    def ingest(
        self,
        *,
        asset_paths: list[Path],
        target_hint: str | None = None,
        correction_text: str | None = None,
        correction_audio_path: Path | None = None,
        explicit_property_id: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        session = self.deps.store.create_session(
            {
                "target_hint": target_hint,
                "status": "received",
                "target_resource": target_hint,
            }
        )
        normalized_assets = self._attach_and_normalize_assets(session["session_id"], asset_paths)
        extraction = self.deps.openai.extract_draft(normalized_assets, target_hint=target_hint)

        draft = self._base_draft(session["session_id"])
        draft.update(
            {
                "status": "extracted",
                "target_resource": extraction.get("target_resource", target_hint or "unsupported"),
                "confidence": extraction.get("confidence"),
                "raw_text": extraction.get("raw_text", ""),
                "contact": extraction.get("contact") or {},
                "property": extraction.get("property") or {},
                "request": extraction.get("request") or {},
                "message": extraction.get("message") or {},
                "validation": {"blocking_errors": [], "warnings": [], "missing_critical_fields": [], "is_blocked": False},
                "zabun_resolution": {},
                "assets": [str(path) for path in normalized_assets],
            }
        )

        if explicit_property_id is not None:
            draft.setdefault("message", {})["property_id"] = explicit_property_id
            draft.setdefault("zabun_resolution", {})["property_id"] = explicit_property_id

        if correction_audio_path:
            transcription = self.deps.openai.transcribe_audio(correction_audio_path)
            correction_text = " ".join(filter(None, [correction_text, transcription.get("transcript")]))
            draft.setdefault("events", []).append({"type": "voice_correction", "transcript": transcription.get("transcript")})

        if correction_text:
            self._apply_text_correction(draft, correction_text)

        version = self.deps.zabun.heartbeat()
        draft["zabun_heartbeat"] = version

        property_option_items = self._load_or_refresh_cache("property_option_items", self.deps.zabun.get_property_option_items)
        contact_option_items = self._load_or_refresh_cache("contact_option_items", self.deps.zabun.get_contact_option_items)

        self._resolve_ids(draft, property_option_items, contact_option_items)
        duplicates = self._search_duplicates(draft)
        draft["duplicates"] = duplicates
        action = self._decide_action(draft, duplicates)
        draft["action"] = action

        validation = self._validate(draft)
        draft["validation"] = validation

        request_plan = self._build_request_plan(draft)
        draft["zabun_request"] = request_plan

        self.deps.store.save_session(draft)

        if validation["is_blocked"] or dry_run:
            return draft

        response = self._submit_request(request_plan)
        draft["status"] = "pushed"
        draft["zabun_response"] = response
        draft["zabun_object_id"] = first_non_empty(
            [
                response.get("auto_id") if isinstance(response, dict) else None,
                response.get("id") if isinstance(response, dict) else None,
                response.get("property_id") if isinstance(response, dict) else None,
                response.get("contact_autoid") if isinstance(response, dict) else None,
            ]
        )
        self.deps.store.save_session(draft)
        return draft

    def _base_draft(self, session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "created_at": utcnow_iso(),
            "status": "received",
            "target_resource": "unsupported",
            "action": "create",
            "contact": {},
            "property": {"address": {}},
            "request": {},
            "message": {},
            "validation": {},
            "zabun_resolution": {},
        }

    def _attach_and_normalize_assets(self, session_id: str, asset_paths: list[Path]) -> list[Path]:
        normalized: list[Path] = []
        asset_dir = self.deps.store.asset_dir(session_id)
        for asset_path in asset_paths:
            copied = copy_with_possible_conversion(asset_path, asset_dir)
            normalized.append(copied)
            self.deps.store.append_event(
                session_id,
                "asset_attached",
                {"path": str(copied), "kind": detect_asset_kind(copied)},
            )
        return normalized

    def _load_or_refresh_cache(self, cache_name: str, loader: Any) -> dict[str, Any]:
        cache_path = self.deps.store.cache_path(cache_name)
        payload = loader()
        dump_json(cache_path, payload)
        return payload

    def _resolve_ids(
        self,
        draft: dict[str, Any],
        property_option_items: dict[str, Any],
        contact_option_items: dict[str, Any],
    ) -> None:
        resolution = draft.setdefault("zabun_resolution", {})
        property_section = draft.setdefault("property", {})
        contact_section = draft.setdefault("contact", {})
        message_section = draft.setdefault("message", {})
        address = property_section.setdefault("address", {})

        resolution["responsible_salesrep_person_id"] = self.deps.zabun_config.responsible_salesrep_person_id
        resolution["country_geo_id"] = self.deps.zabun_config.default_country_geo_id

        if draft["target_resource"] == "property":
            resolution["status_id"], _ = best_option_match(
                property_option_items.get("status", []),
                property_section.get("status_label"),
                self.deps.zabun_config.default_property_status_id,
            )
            resolution["transaction_id"], _ = best_option_match(
                property_option_items.get("transactions", []),
                property_section.get("transaction_label"),
            )
            resolution["type_id"], _ = best_option_match(
                property_option_items.get("types", []),
                property_section.get("type_label"),
            )
            resolution["mandate_type_id"], _ = best_option_match(
                property_option_items.get("mandate_types", []),
                property_section.get("mandate_type_label"),
                self.deps.zabun_config.default_mandate_type_id,
            )
            if self.deps.zabun_config.default_office_autoid is not None:
                property_section["office_autoid"] = self.deps.zabun_config.default_office_autoid
            city = address.get("city")
            postal_code = address.get("postal_code")
            if city:
                city_result = self.deps.zabun.search_cities(city, zip_code=postal_code, country_geo_id=resolution["country_geo_id"])
                candidates = city_result.get("cities", [])
                if candidates:
                    first = candidates[0]
                    resolution["city_geo_id"] = first.get("id") or first.get("auto_id")

        if draft["target_resource"] in {"contact", "contactmessage", "contactrequest"}:
            resolution["title_id"], _ = best_option_match(
                contact_option_items.get("titles", []),
                contact_section.get("title_label"),
                self.deps.zabun_config.default_contact_title_id,
            )
            resolution["status_id"], _ = best_option_match(
                contact_option_items.get("status", []),
                contact_section.get("status_label"),
                self.deps.zabun_config.default_contact_status_id,
            )

        if draft["target_resource"] == "contactrequest":
            request = draft.setdefault("request", {})
            request["transaction_ids"] = [
                match_id
                for label in request.get("transaction_labels", [])
                for match_id, _ in [best_option_match(property_option_items.get("transactions", []), label)]
                if match_id is not None
            ]
            request["type_ids"] = [
                match_id
                for label in request.get("type_labels", [])
                for match_id, _ in [best_option_match(property_option_items.get("types", []), label)]
                if match_id is not None
            ]
            city_ids = []
            for label in request.get("city_labels", []):
                city_result = self.deps.zabun.search_cities(label, country_geo_id=resolution["country_geo_id"])
                candidates = city_result.get("cities", [])
                if candidates:
                    city_ids.append(candidates[0].get("id") or candidates[0].get("auto_id"))
            request["city_ids"] = [city_id for city_id in city_ids if city_id is not None]

        if draft["target_resource"] == "contactmessage" and not resolution.get("property_id"):
            explicit_id = message_section.get("property_id")
            if explicit_id:
                resolution["property_id"] = explicit_id
            else:
                property_search_text = self._property_search_text(draft)
                if property_search_text:
                    result = self.deps.zabun.search_properties(full_text=property_search_text)
                    matches = result.get("properties", [])
                    if matches:
                        first = matches[0]
                        resolution["property_id"] = first.get("auto_id") or first.get("id")

        mobile = contact_section.get("mobile")
        if mobile and not contact_section.get("mobile_cc"):
            local_number, country_cc = split_mobile_cc(mobile)
            contact_section["mobile"] = local_number or mobile
            if country_cc:
                contact_section["mobile_cc"] = country_cc

        if not contact_section.get("language"):
            contact_section["language"] = "FR"

        if draft["target_resource"] == "property":
            property_section["show"] = self.deps.runtime.default_property_show

    def _search_duplicates(self, draft: dict[str, Any]) -> dict[str, Any]:
        target = draft["target_resource"]
        duplicates: dict[str, Any] = {"contacts": [], "properties": []}
        if target in {"contact", "contactmessage", "contactrequest"}:
            contact = draft.get("contact", {})
            search_parts = [contact.get("email"), contact.get("mobile"), " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")]))]
            full_text = " ".join(part for part in search_parts if part)
            if full_text:
                result = self.deps.zabun.search_contacts(full_text=full_text)
                duplicates["contacts"] = result.get("contacts", [])
        if target == "property":
            property_search_text = self._property_search_text(draft)
            if property_search_text:
                result = self.deps.zabun.search_properties(
                    full_text=property_search_text,
                    transaction_ids=[draft["zabun_resolution"]["transaction_id"]] if draft["zabun_resolution"].get("transaction_id") else None,
                    type_ids=[draft["zabun_resolution"]["type_id"]] if draft["zabun_resolution"].get("type_id") else None,
                )
                duplicates["properties"] = result.get("properties", [])
        return duplicates

    def _decide_action(self, draft: dict[str, Any], duplicates: dict[str, Any]) -> str:
        target = draft["target_resource"]
        if target == "property" and duplicates.get("properties"):
            first = duplicates["properties"][0]
            draft["zabun_resolution"]["property_id"] = first.get("auto_id") or first.get("id")
            return "patch"
        if target == "contact" and duplicates.get("contacts"):
            first = duplicates["contacts"][0]
            draft["zabun_resolution"]["contact_autoid"] = first.get("auto_id") or first.get("id")
            return "patch"
        return "create"

    def _validate(self, draft: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []
        target = draft["target_resource"]
        resolution = draft.get("zabun_resolution", {})
        contact = draft.get("contact", {})
        property_section = draft.get("property", {})
        address = property_section.get("address", {})
        message = draft.get("message", {})

        if target == "unsupported":
            errors.append("Unsupported target resource")

        if not draft.get("zabun_heartbeat"):
            errors.append("Zabun heartbeat missing")

        if target == "property":
            required_pairs = [
                ("transaction_id", resolution.get("transaction_id")),
                ("type_id", resolution.get("type_id")),
                ("status_id", resolution.get("status_id")),
                ("mandate_type_id", resolution.get("mandate_type_id")),
                ("responsible_salesrep_person_id", resolution.get("responsible_salesrep_person_id")),
                ("city_geo_id", resolution.get("city_geo_id")),
                ("country_geo_id", resolution.get("country_geo_id")),
                ("address.number", address.get("number")),
                ("address.street", address.get("street")),
                ("mandate_start", property_section.get("mandate_start")),
            ]
            for field_name, value in required_pairs:
                if value in (None, ""):
                    missing.append(field_name)
            if property_section.get("price") in (None, ""):
                warnings.append("Property price is missing and may be required by Zabun")

        if target == "contact":
            required_pairs = [
                ("contact.last_name", contact.get("last_name")),
                ("title_id", resolution.get("title_id")),
                ("status_id", resolution.get("status_id")),
                ("responsible_salesrep_person_id", resolution.get("responsible_salesrep_person_id")),
            ]
            for field_name, value in required_pairs:
                if value in (None, ""):
                    missing.append(field_name)

        if target == "contactmessage":
            if not contact.get("last_name"):
                missing.append("contact.last_name")
            if not contact.get("language"):
                missing.append("contact.language")
            if not message.get("text"):
                missing.append("message.text")
            if not resolution.get("property_id"):
                missing.append("property_id")
            if not contact.get("email") and not (contact.get("mobile") and contact.get("mobile_cc")):
                missing.append("contact.email_or_phone")
            if contact.get("marketing_opt_in") is True:
                warnings.append("marketing_opt_in=true requires explicit consent proof")
            if contact.get("mailing_opt_in") is True:
                warnings.append("mailing_opt_in=true requires explicit consent proof")

        if target == "contactrequest":
            if not contact.get("last_name"):
                missing.append("contact.last_name")
            if not contact.get("language"):
                missing.append("contact.language")
            request = draft.get("request", {})
            if not any(
                [
                    request.get("price_min"),
                    request.get("price_max"),
                    request.get("city_labels"),
                    request.get("type_labels"),
                    request.get("transaction_labels"),
                ]
            ):
                missing.append("request.core_search")

        if missing:
            errors.append("Missing critical fields for {target}".format(target=target))

        return {
            "is_blocked": bool(errors),
            "blocking_errors": errors,
            "warnings": warnings,
            "missing_critical_fields": missing,
        }

    def _build_request_plan(self, draft: dict[str, Any]) -> dict[str, Any]:
        target = draft["target_resource"]
        action = draft.get("action", "create")
        if target == "property":
            payload = self._build_property_payload(draft)
            if action == "patch":
                endpoint = "/api/v1/property/{property_id}".format(property_id=draft["zabun_resolution"]["property_id"])
                return {"method": "PATCH", "endpoint": endpoint, "payload": payload}
            return {"method": "POST", "endpoint": "/api/v1/property", "payload": payload}
        if target == "contact":
            payload = self._build_contact_payload(draft)
            if action == "patch":
                endpoint = "/api/v1/contact/{contact_autoid}".format(contact_autoid=draft["zabun_resolution"]["contact_autoid"])
                return {"method": "PATCH", "endpoint": endpoint, "payload": payload}
            return {"method": "POST", "endpoint": "/api/v1/contact", "payload": payload}
        if target == "contactmessage":
            return {"method": "POST", "endpoint": "/api/v1/contactmessage", "payload": self._build_contactmessage_payload(draft)}
        if target == "contactrequest":
            return {"method": "POST", "endpoint": "/api/v1/contactrequest", "payload": self._build_contactrequest_payload(draft)}
        raise ValidationError("Unsupported request target: {target}".format(target=target))

    def _build_property_payload(self, draft: dict[str, Any]) -> dict[str, Any]:
        property_section = draft["property"]
        address = property_section.get("address", {})
        resolution = draft["zabun_resolution"]
        payload = {
            "office_autoid": property_section.get("office_autoid"),
            "transaction_id": resolution.get("transaction_id"),
            "type_id": resolution.get("type_id"),
            "status_id": resolution.get("status_id"),
            "show": bool(property_section.get("show")),
            "mandate_type_id": resolution.get("mandate_type_id"),
            "mandate_start": property_section.get("mandate_start"),
            "price": property_section.get("price"),
            "responsible_salesrep_person_id": resolution.get("responsible_salesrep_person_id"),
            "title": {"fr": property_section.get("title")} if property_section.get("title") else None,
            "address": {
                "city_geo_id": resolution.get("city_geo_id"),
                "number": address.get("number"),
                "box": address.get("box"),
                "country_geo_id": resolution.get("country_geo_id"),
                "street_translated": {"fr": address.get("street")} if address.get("street") else None,
            },
        }
        return cleanup_none(payload)

    def _build_contact_payload(self, draft: dict[str, Any]) -> dict[str, Any]:
        contact = dict(draft["contact"])
        resolution = draft["zabun_resolution"]
        payload = {
            "first_name": contact.get("first_name"),
            "last_name": contact.get("last_name"),
            "title_id": resolution.get("title_id"),
            "status_id": resolution.get("status_id"),
            "responsible_salesrep_person_id": resolution.get("responsible_salesrep_person_id"),
            "email": contact.get("email"),
            "mobile": contact.get("mobile"),
            "mobile_cc": contact.get("mobile_cc"),
            "language": contact.get("language"),
        }
        return cleanup_none(payload)

    def _build_contactmessage_payload(self, draft: dict[str, Any]) -> dict[str, Any]:
        contact = dict(draft["contact"])
        message = dict(draft["message"])
        resolution = draft["zabun_resolution"]
        payload = {
            "contact": {
                "email": contact.get("email"),
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "marketing_opt_in": contact.get("marketing_opt_in"),
                "mailing_opt_in": contact.get("mailing_opt_in"),
                "phone": contact.get("mobile"),
                "phone_cc": contact.get("mobile_cc"),
                "language": contact.get("language"),
            },
            "message": {
                "text": message.get("text"),
                "property_id": resolution.get("property_id") or message.get("property_id"),
                "info": message.get("info"),
            },
        }
        return cleanup_none(payload)

    def _build_contactrequest_payload(self, draft: dict[str, Any]) -> dict[str, Any]:
        contact = dict(draft["contact"])
        request = dict(draft["request"])
        resolution = draft["zabun_resolution"]
        payload = {
            "contact": {
                "email": contact.get("email"),
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "phone": contact.get("mobile"),
                "phone_cc": contact.get("mobile_cc"),
                "language": contact.get("language"),
            },
            "request": {
                "price": {
                    "min": request.get("price_min"),
                    "max": request.get("price_max"),
                },
                "city_ids": request.get("city_ids"),
                "type_ids": request.get("type_ids"),
                "transaction_ids": request.get("transaction_ids"),
                "rooms": request.get("rooms"),
                "responsible_salesrep_person_id": resolution.get("responsible_salesrep_person_id"),
            },
        }
        return cleanup_none(payload)

    def _submit_request(self, plan: dict[str, Any]) -> dict[str, Any]:
        method = plan["method"]
        payload = plan["payload"]
        endpoint = plan["endpoint"]
        if endpoint == "/api/v1/property" and method == "POST":
            return self.deps.zabun.create_property(payload)
        if endpoint.startswith("/api/v1/property/") and method == "PATCH":
            property_id = int(endpoint.rsplit("/", 1)[-1])
            return self.deps.zabun.patch_property(property_id, payload)
        if endpoint == "/api/v1/contact" and method == "POST":
            return self.deps.zabun.create_contact(payload)
        if endpoint.startswith("/api/v1/contact/") and method == "PATCH":
            contact_autoid = int(endpoint.rsplit("/", 1)[-1])
            return self.deps.zabun.patch_contact(contact_autoid, payload)
        if endpoint == "/api/v1/contactmessage":
            return self.deps.zabun.create_contactmessage(payload)
        if endpoint == "/api/v1/contactrequest":
            return self.deps.zabun.create_contactrequest(payload)
        raise ValidationError("Unsupported request plan: {plan}".format(plan=plan))

    def _apply_text_correction(self, draft: dict[str, Any], correction_text: str) -> None:
        folded = normalize_text(correction_text)
        draft.setdefault("corrections", []).append({"type": "text", "text": correction_text})
        if "vente" in folded or "sell" in folded:
            draft.setdefault("property", {})["transaction_label"] = "vente"
        if "location" in folded or "rent" in folded:
            draft.setdefault("property", {})["transaction_label"] = "location"
        if "appartement" in folded:
            draft.setdefault("property", {})["type_label"] = "appartement"
        if "maison" in folded:
            draft.setdefault("property", {})["type_label"] = "maison"

    def _property_search_text(self, draft: dict[str, Any]) -> str:
        address = draft.get("property", {}).get("address", {})
        parts = [address.get("street"), address.get("number"), address.get("postal_code"), address.get("city")]
        return " ".join(str(part) for part in parts if part)
