from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".mp4"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt", ".md"}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    return "sess_" + uuid.uuid4().hex[:12]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    folded = unicodedata.normalize("NFKD", str(value))
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower().strip()
    lowered = re.sub(r"[\s/_-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered)


def strip_phone(value: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", value or "")
    if cleaned.startswith("00"):
        return "+" + cleaned[2:]
    return cleaned


def split_mobile_cc(phone: str | None) -> tuple[str | None, str | None]:
    if not phone:
        return None, None
    cleaned = strip_phone(phone)
    if cleaned.startswith("+32"):
        national = cleaned[3:]
        if national.startswith("0"):
            national = national[1:]
        return national or None, "32"
    return cleaned or None, None


def detect_asset_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("image/"):
        return "image"
    if mime and mime.startswith("audio/"):
        return "audio"
    return "binary"


def mime_type_for_path(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type or "application/octet-stream"


def file_to_data_url(path: Path) -> str:
    mime_type = mime_type_for_path(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:{mime};base64,{payload}".format(mime=mime_type, payload=encoded)


def copy_with_possible_conversion(source: Path, destination_dir: Path) -> Path:
    ensure_dir(destination_dir)
    suffix = source.suffix.lower()
    destination = destination_dir / source.name
    if suffix in {".heic", ".heif"} and shutil.which("sips"):
        converted = destination.with_suffix(".jpg")
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(source), "--out", str(converted)],
            check=True,
            capture_output=True,
            text=True,
        )
        return converted
    shutil.copy2(source, destination)
    return destination


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def dump_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def first_non_empty(values: Iterable[Any]) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def json_from_markdown_blob(raw_text: str) -> dict[str, Any]:
    if not raw_text:
        return {}
    candidate = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    return json.loads(candidate)


def extract_multilingual_value(node: Any) -> list[str]:
    values: list[str] = []
    if isinstance(node, str):
        values.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            values.extend(extract_multilingual_value(value))
    elif isinstance(node, list):
        for value in node:
            values.extend(extract_multilingual_value(value))
    return [value for value in values if value]


def option_label_candidates(option_item: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in ("name", "title", "label", "value"):
        if key in option_item and option_item[key] is not None:
            labels.extend(extract_multilingual_value(option_item[key]))
    for key in ("short_name", "description"):
        if key in option_item and isinstance(option_item[key], str):
            labels.append(option_item[key])
    return list(dict.fromkeys(labels))


def best_option_match(
    options: list[dict[str, Any]],
    label: str | None,
    fallback_id: int | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    if not options:
        return fallback_id, None
    if not label:
        if fallback_id is not None:
            for option in options:
                option_id = option.get("id") or option.get("auto_id")
                if option_id == fallback_id:
                    return fallback_id, option
        return fallback_id, None

    needle = normalize_text(label)
    best: tuple[int, dict[str, Any]] | None = None
    best_score = -1
    for option in options:
        option_id = option.get("id") or option.get("auto_id")
        for candidate in option_label_candidates(option):
            candidate_folded = normalize_text(candidate)
            score = 0
            if needle == candidate_folded:
                score = 100
            elif needle and needle in candidate_folded:
                score = 70
            elif candidate_folded and candidate_folded in needle:
                score = 50
            if score > best_score and option_id is not None:
                best_score = score
                best = (int(option_id), option)
    if best:
        return best
    return fallback_id, None


def cleanup_none(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            normalized = cleanup_none(value)
            if normalized not in (None, "", [], {}):
                cleaned[key] = normalized
        return cleaned
    if isinstance(obj, list):
        cleaned_items = []
        for value in obj:
            normalized = cleanup_none(value)
            if normalized not in (None, "", [], {}):
                cleaned_items.append(normalized)
        return cleaned_items
    return obj


def getenv_int(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)
