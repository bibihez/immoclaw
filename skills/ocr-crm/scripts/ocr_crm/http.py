from __future__ import annotations

from typing import Any

import requests

from .exceptions import ExternalServiceError


def json_request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
    json_payload: dict[str, Any] | None = None,
    expected_status: tuple[int, ...] = (200,),
) -> Any:
    response = session.request(
        method=method,
        url=url,
        headers=headers,
        json=json_payload,
        timeout=timeout,
    )
    if response.status_code not in expected_status:
        raise ExternalServiceError(
            "HTTP {status} from {url}: {body}".format(
                status=response.status_code,
                url=url,
                body=response.text[:2000],
            )
        )
    if not response.text:
        return None
    if "application/json" in response.headers.get("Content-Type", ""):
        return response.json()
    return response.text
