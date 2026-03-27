from __future__ import annotations

from typing import Any

import requests

from .config import ZabunConfig
from .http import json_request


class ZabunClient:
    def __init__(self, config: ZabunConfig, timeout: int = 60) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()

    def _url(self, path: str) -> str:
        return self.config.base_url + path

    def _headers(self) -> dict[str, str]:
        return self.config.headers()

    def heartbeat(self) -> str:
        response = self.session.get(
            self._url("/auth/v1/heartbeat"),
            headers={key: value for key, value in self._headers().items() if key != "Content-Type"},
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Exception("Heartbeat failed: {status} {body}".format(status=response.status_code, body=response.text))
        return response.text.strip().strip('"')

    def get_property_option_items(self) -> dict[str, Any]:
        return json_request(
            self.session,
            "GET",
            self._url("/api/v1/property/option_items"),
            headers=self._headers(),
            timeout=self.timeout,
        )

    def get_contact_option_items(self) -> dict[str, Any]:
        return json_request(
            self.session,
            "GET",
            self._url("/api/v1/contact/option_items"),
            headers=self._headers(),
            timeout=self.timeout,
        )

    def search_cities(self, city_text: str, zip_code: str | None = None, country_geo_id: int = 23) -> dict[str, Any]:
        filtering: dict[str, Any] = {"city_text": city_text, "country_geo_ids": [country_geo_id]}
        if zip_code:
            filtering["zip_codes"] = [zip_code]
        payload = {
            "paging": {"page": 0, "size": 20},
            "filtering": filtering,
        }
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/geo/cities/search"),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def search_contacts(self, *, full_text: str, active: bool = True) -> dict[str, Any]:
        payload = {
            "paging": {"page": 0, "size": 20},
            "filtering": {"full_text": full_text, "active": active},
        }
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/contact/search"),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def search_properties(
        self,
        *,
        full_text: str,
        active: bool = True,
        transaction_ids: list[int] | None = None,
        type_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        filtering: dict[str, Any] = {"full_text": full_text, "active": active}
        if transaction_ids:
            filtering["transaction_ids"] = transaction_ids
        if type_ids:
            filtering["type_ids"] = type_ids
        payload = {
            "paging": {"page": 0, "size": 20},
            "filtering": filtering,
        }
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/property/search"),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def create_property(self, payload: dict[str, Any], extended: bool = True) -> dict[str, Any]:
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/property?extended={value}".format(value="true" if extended else "false")),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def patch_property(self, property_id: int, payload: dict[str, Any], extended: bool = True) -> dict[str, Any]:
        return json_request(
            self.session,
            "PATCH",
            self._url("/api/v1/property/{property_id}?extended={value}".format(property_id=property_id, value="true" if extended else "false")),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def create_contact(self, payload: dict[str, Any], extended: bool = True) -> dict[str, Any]:
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/contact?extended={value}".format(value="true" if extended else "false")),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def patch_contact(self, contact_autoid: int, payload: dict[str, Any], extended: bool = True) -> dict[str, Any]:
        return json_request(
            self.session,
            "PATCH",
            self._url("/api/v1/contact/{contact_autoid}?extended={value}".format(contact_autoid=contact_autoid, value="true" if extended else "false")),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def create_contactmessage(self, payload: dict[str, Any]) -> dict[str, Any]:
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/contactmessage"),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )

    def create_contactrequest(self, payload: dict[str, Any]) -> dict[str, Any]:
        return json_request(
            self.session,
            "POST",
            self._url("/api/v1/contactrequest"),
            headers=self._headers(),
            timeout=self.timeout,
            json_payload=payload,
        )
