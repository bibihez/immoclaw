from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import ConfigurationError
from .utils import ensure_dir, getenv_int


@dataclass
class ZabunConfig:
    base_url: str
    x_client_id: str
    x_user_id: str
    api_key: str
    client_id: str
    server_id: str
    accept_language: str = "fr,nl"
    responsible_salesrep_person_id: int | None = None
    default_property_status_id: int | None = 1
    default_contact_status_id: int | None = 1
    default_mandate_type_id: int | None = 1
    default_contact_title_id: int | None = None
    default_office_autoid: int | None = None
    default_country_geo_id: int = 23

    @classmethod
    def from_env(cls) -> "ZabunConfig":
        required = {
            "base_url": os.getenv("ZABUN_BASE_URL", "https://gateway-cmsapi.v2.zabun.be"),
            "x_client_id": os.getenv("ZABUN_X_CLIENT_ID"),
            "x_user_id": os.getenv("ZABUN_X_USER_ID"),
            "api_key": os.getenv("ZABUN_API_KEY"),
            "client_id": os.getenv("ZABUN_CLIENT_ID"),
            "server_id": os.getenv("ZABUN_SERVER_ID"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ConfigurationError(
                "Missing Zabun environment variables: {names}".format(names=", ".join(sorted(missing)))
            )
        return cls(
            base_url=required["base_url"].rstrip("/"),
            x_client_id=str(required["x_client_id"]),
            x_user_id=str(required["x_user_id"]),
            api_key=str(required["api_key"]),
            client_id=str(required["client_id"]),
            server_id=str(required["server_id"]),
            accept_language=os.getenv("ZABUN_ACCEPT_LANGUAGE", "fr,nl"),
            responsible_salesrep_person_id=getenv_int("ZABUN_RESPONSIBLE_SALESREP_PERSON_ID"),
            default_property_status_id=getenv_int("ZABUN_DEFAULT_PROPERTY_STATUS_ID", 1),
            default_contact_status_id=getenv_int("ZABUN_DEFAULT_CONTACT_STATUS_ID", 1),
            default_mandate_type_id=getenv_int("ZABUN_DEFAULT_MANDATE_TYPE_ID", 1),
            default_contact_title_id=getenv_int("ZABUN_DEFAULT_CONTACT_TITLE_ID"),
            default_office_autoid=getenv_int("ZABUN_DEFAULT_OFFICE_AUTOID"),
            default_country_geo_id=getenv_int("ZABUN_DEFAULT_COUNTRY_GEO_ID", 23) or 23,
        )

    def headers(self) -> dict[str, str]:
        return {
            "X-CLIENT-ID": self.x_client_id,
            "X-USER-ID": self.x_user_id,
            "api_key": self.api_key,
            "client_id": self.client_id,
            "server_id": self.server_id,
            "Accept-Language": self.accept_language,
            "Content-Type": "application/json",
        }


@dataclass
class OpenAIConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    vision_model: str = "gpt-4o-mini"
    transcription_model: str = "gpt-4o-mini-transcribe"

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ConfigurationError("Missing OPENAI_API_KEY environment variable")
        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            vision_model=os.getenv("OCR_CRM_OPENAI_VISION_MODEL", "gpt-4o-mini"),
            transcription_model=os.getenv("OCR_CRM_OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
        )

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": "Bearer {token}".format(token=self.api_key),
            "Content-Type": "application/json",
        }


@dataclass
class RuntimeConfig:
    state_dir: Path
    require_agent_confirmation: bool = True
    default_property_show: bool = False
    request_timeout_seconds: int = 60
    duplicate_threshold: float = 0.9
    evidence_threshold: float = 0.5
    raw_text_limit: int = 12000
    supported_image_extensions: tuple[str, ...] = field(default_factory=lambda: (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"))

    @classmethod
    def from_env(cls, skill_dir: Path) -> "RuntimeConfig":
        state_dir = Path(os.getenv("OCR_CRM_STATE_DIR", str(skill_dir / "state")))
        ensure_dir(state_dir)
        return cls(
            state_dir=state_dir,
            require_agent_confirmation=os.getenv("OCR_CRM_REQUIRE_AGENT_CONFIRMATION", "true").lower() != "false",
            default_property_show=os.getenv("OCR_CRM_DEFAULT_PROPERTY_SHOW", "false").lower() == "true",
            request_timeout_seconds=int(os.getenv("OCR_CRM_HTTP_TIMEOUT_SECONDS", "60")),
            duplicate_threshold=float(os.getenv("OCR_CRM_DUPLICATE_THRESHOLD", "0.9")),
            evidence_threshold=float(os.getenv("OCR_CRM_EVIDENCE_THRESHOLD", "0.5")),
            raw_text_limit=int(os.getenv("OCR_CRM_RAW_TEXT_LIMIT", "12000")),
        )
