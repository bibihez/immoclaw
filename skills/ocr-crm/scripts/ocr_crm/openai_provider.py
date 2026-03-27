from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from .config import OpenAIConfig
from .exceptions import ExternalServiceError
from .utils import file_to_data_url, json_from_markdown_blob, mime_type_for_path


EXTRACTION_SCHEMA_EXAMPLE = {
    "target_resource": "property",
    "confidence": 0.0,
    "raw_text": "",
    "contact": {
        "first_name": None,
        "last_name": None,
        "email": None,
        "mobile": None,
        "language": None,
    },
    "property": {
        "title": None,
        "price": None,
        "show": None,
        "transaction_label": None,
        "type_label": None,
        "status_label": None,
        "mandate_type_label": None,
        "mandate_start": None,
        "address": {
            "street": None,
            "number": None,
            "box": None,
            "postal_code": None,
            "city": None,
        },
    },
    "message": {
        "text": None,
        "property_id": None,
        "info": [],
    },
    "request": {
        "price_min": None,
        "price_max": None,
        "city_labels": [],
        "type_labels": [],
        "transaction_labels": [],
        "rooms": None,
    },
}


class OpenAIProvider:
    def __init__(self, config: OpenAIConfig, timeout: int = 60) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()

    def _responses_url(self) -> str:
        return self.config.base_url + "/responses"

    def _transcriptions_url(self) -> str:
        return self.config.base_url + "/audio/transcriptions"

    def extract_draft(self, asset_paths: list[Path], target_hint: str | None = None) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": self._extraction_prompt(target_hint=target_hint),
            }
        ]
        for asset_path in asset_paths:
            suffix = asset_path.suffix.lower()
            mime_type = mime_type_for_path(asset_path)
            if suffix == ".pdf":
                content.append(
                    {
                        "type": "input_file",
                        "filename": asset_path.name,
                        "file_data": file_to_data_url(asset_path),
                    }
                )
            elif mime_type.startswith("image/"):
                content.append(
                    {
                        "type": "input_image",
                        "image_url": file_to_data_url(asset_path),
                    }
                )
            else:
                text = asset_path.read_text() if mime_type.startswith("text/") else asset_path.name
                content.append({"type": "input_text", "text": text})

        payload = {
            "model": self.config.vision_model,
            "input": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        }
        response = self.session.post(
            self._responses_url(),
            headers={
                "Authorization": "Bearer {token}".format(token=self.config.api_key),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise ExternalServiceError(
                "OpenAI extraction failed: {status} {body}".format(
                    status=response.status_code,
                    body=response.text[:2000],
                )
            )
        data = response.json()
        output_text = data.get("output_text") or self._fallback_output_text(data)
        parsed = json_from_markdown_blob(output_text)
        if "raw_text" not in parsed:
            parsed["raw_text"] = output_text
        return parsed

    def transcribe_audio(self, audio_path: Path) -> dict[str, Any]:
        with audio_path.open("rb") as file_handle:
            response = self.session.post(
                self._transcriptions_url(),
                headers={"Authorization": "Bearer {token}".format(token=self.config.api_key)},
                data={"model": self.config.transcription_model},
                files={"file": (audio_path.name, file_handle, mime_type_for_path(audio_path))},
                timeout=self.timeout,
            )
        if response.status_code != 200:
            raise ExternalServiceError(
                "OpenAI transcription failed: {status} {body}".format(
                    status=response.status_code,
                    body=response.text[:2000],
                )
            )
        data = response.json()
        return {
            "transcript": data.get("text", ""),
            "confidence": data.get("confidence"),
            "raw_response": data,
        }

    def _fallback_output_text(self, payload: dict[str, Any]) -> str:
        output_parts: list[str] = []
        for output_item in payload.get("output", []):
            for content_item in output_item.get("content", []):
                if content_item.get("type") in {"output_text", "text"} and content_item.get("text"):
                    output_parts.append(content_item["text"])
        return "\n".join(output_parts)

    def _extraction_prompt(self, target_hint: str | None = None) -> str:
        schema = json.dumps(EXTRACTION_SCHEMA_EXAMPLE, indent=2)
        hint_line = "Preferred target resource: {hint}.".format(hint=target_hint) if target_hint else "No target hint."
        return """
You extract OCR CRM data for a Belgian real-estate workflow.
{hint_line}

Return JSON only. No markdown, no prose.
Use exactly these target resources: property, contact, contactmessage, contactrequest, unsupported.
Never invent facts. Use null for missing values.
If a value is ambiguous, keep the safest literal candidate.
If the document contains a lead or inquiry linked to a known property, use contactmessage.
If the document contains a buyer search brief, use contactrequest.

Required JSON shape example:
{schema}
""".strip().format(hint_line=hint_line, schema=schema)
