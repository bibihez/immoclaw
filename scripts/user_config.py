#!/usr/bin/env python3
"""Load the minimal runtime config from USER.md and environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UserConfig:
    agent_name: str = ""
    agent_email: str = ""
    agentmail_inbox_id: str = ""
    agentmail_api_key: str = ""
    agentmail_webhook_secret: str = ""
    signature_fr: str = ""
    signature_nl: str = ""
    form_fr_prefill_url_template: str = ""
    form_nl_prefill_url_template: str = ""
    calcom_api_key: str = ""
    calcom_base_url: str = "https://api.cal.com/v2"
    calcom_api_version: str = "2024-08-13"
    calcom_username: str = ""
    calcom_private_visit_event_slug: str = "visite-privee-45min"
    calcom_open_house_event_slug: str = "porte-ouverte-30min"
    calcom_webhook_secret: str = ""
    webhook_base_url: str = ""
    working_hours: str = "09:00-19:00"


def _read_user_md(workspace_dir: str | None = None) -> str:
    base = Path(workspace_dir) if workspace_dir else Path(__file__).resolve().parents[1]
    return (base / "USER.md").read_text(encoding="utf-8")


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def _extract_markdown_codeblock(md: str, key: str) -> str:
    pattern = rf"- \*\*{re.escape(key)}:\*\* \|\n(?P<body>(?:[ \t]{{4,}}.*\n?)*)"
    match = re.search(pattern, md)
    if not match:
        return ""
    body = match.group("body")
    return re.sub(r"^[ \t]{4}", "", body, flags=re.MULTILINE).rstrip()


def _extract_markdown_field(md: str, field: str) -> str:
    quoted = re.search(rf"- \*\*{re.escape(field)}:\*\*\s*\"(?P<v>[^\"]*)\"", md)
    if quoted:
        return quoted.group("v").strip()
    plain = re.search(rf"- \*\*{re.escape(field)}:\*\*\s*(?P<v>[^\n]*)", md)
    if plain:
        return plain.group("v").strip().strip('"')
    return ""


def _extract_yaml_section(md: str, section_name: str) -> str:
    pattern = rf"^{re.escape(section_name)}:\s*\n(?P<body>(?:^[ \t].*\n?)*)"
    match = re.search(pattern, md, re.MULTILINE)
    return match.group("body") if match else ""


def _extract_yaml_scalar(section: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(?P<v>[^\n#]*)", section, re.MULTILINE)
    if not match:
        return ""
    return match.group("v").strip().strip('"').strip("'")


def _extract_yaml_codeblock(section: str, key: str) -> str:
    pattern = rf"^\s*{re.escape(key)}:\s*\|\n(?P<body>(?:^[ \t]{{4,}}.*\n?)*)"
    match = re.search(pattern, section, re.MULTILINE)
    if not match:
        return ""
    body = match.group("body")
    return re.sub(r"^[ \t]{4}", "", body, flags=re.MULTILINE).rstrip()


def load_user_config(workspace_dir: str | None = None) -> UserConfig:
    md = _read_user_md(workspace_dir)

    agent_section = _extract_yaml_section(md, "agent")
    agentmail_section = _extract_yaml_section(md, "agentmail")
    calcom_section = _extract_yaml_section(md, "calcom")
    google_section = _extract_yaml_section(md, "google")
    forms_section = _extract_yaml_section(md, "forms")
    qualification_section = _extract_yaml_section(forms_section, "qualification")
    preferences_section = _extract_yaml_section(md, "preferences")
    signature_section = _extract_yaml_section(md, "signature")
    webhooks_section = _extract_yaml_section(md, "webhooks")

    agent_name = _first_non_empty(
        _extract_yaml_scalar(agent_section, "name"),
        _extract_markdown_field(md, "name"),
    )
    agent_email = _first_non_empty(
        _extract_yaml_scalar(agent_section, "email"),
        _extract_yaml_scalar(google_section, "email"),
        _extract_markdown_field(md, "email"),
    )
    agentmail_inbox_id = _first_non_empty(
        _extract_yaml_scalar(agentmail_section, "inbox_id"),
        _extract_markdown_field(md, "inbox_id"),
    )
    agentmail_api_key = _first_non_empty(
        _extract_yaml_scalar(agentmail_section, "api_key"),
        _extract_markdown_field(md, "api_key"),
    )
    agentmail_webhook_secret = _first_non_empty(
        _extract_yaml_scalar(webhooks_section, "agentmail_secret"),
        _extract_markdown_field(md, "agentmail_webhook_secret"),
    )
    signature_fr = _first_non_empty(
        _extract_yaml_codeblock(signature_section, "fr"),
        _extract_markdown_codeblock(md, "fr"),
    )
    signature_nl = _first_non_empty(
        _extract_yaml_codeblock(signature_section, "nl"),
        _extract_markdown_codeblock(md, "nl"),
    )
    form_fr_prefill_url_template = _first_non_empty(
        _extract_yaml_scalar(qualification_section, "fr_prefill_url_template"),
        _extract_markdown_field(md, "fr_prefill_url_template"),
    )
    form_nl_prefill_url_template = _first_non_empty(
        _extract_yaml_scalar(qualification_section, "nl_prefill_url_template"),
        _extract_markdown_field(md, "nl_prefill_url_template"),
    )
    calcom_api_key = _first_non_empty(
        _extract_yaml_scalar(calcom_section, "api_key"),
        _extract_markdown_field(md, "calcom_api_key"),
    )
    calcom_base_url = _first_non_empty(
        _extract_yaml_scalar(calcom_section, "base_url"),
        _extract_markdown_field(md, "calcom_base_url"),
        "https://api.cal.com/v2",
    )
    calcom_api_version = _first_non_empty(
        _extract_yaml_scalar(calcom_section, "api_version"),
        _extract_markdown_field(md, "calcom_api_version"),
        "2024-08-13",
    )
    calcom_username = _first_non_empty(
        _extract_yaml_scalar(calcom_section, "username"),
        _extract_markdown_field(md, "username"),
    )
    calcom_private_visit_event_slug = _first_non_empty(
        _extract_yaml_scalar(calcom_section, "private_visit_event_slug"),
        _extract_markdown_field(md, "private_visit_event_slug"),
        "visite-privee-45min",
    )
    calcom_open_house_event_slug = _first_non_empty(
        _extract_yaml_scalar(calcom_section, "open_house_event_slug"),
        _extract_markdown_field(md, "open_house_event_slug"),
        "porte-ouverte-30min",
    )
    calcom_webhook_secret = _first_non_empty(
        _extract_yaml_scalar(webhooks_section, "calcom_secret"),
        _extract_markdown_field(md, "calcom_webhook_secret"),
    )
    webhook_base_url = _first_non_empty(
        _extract_yaml_scalar(webhooks_section, "public_base_url"),
        _extract_markdown_field(md, "webhook_base_url"),
    )
    working_hours = _first_non_empty(
        _extract_yaml_scalar(preferences_section, "working_hours"),
        _extract_markdown_field(md, "working_hours"),
        "09:00-19:00",
    )

    return UserConfig(
        agent_name=os.getenv("AGENT_NAME", agent_name),
        agent_email=os.getenv("AGENT_EMAIL", agent_email),
        agentmail_inbox_id=os.getenv("AGENTMAIL_INBOX_ID", agentmail_inbox_id),
        agentmail_api_key=os.getenv("AGENTMAIL_API_KEY", agentmail_api_key),
        agentmail_webhook_secret=os.getenv("AGENTMAIL_WEBHOOK_SECRET", agentmail_webhook_secret),
        signature_fr=os.getenv("SIGNATURE_FR", signature_fr),
        signature_nl=os.getenv("SIGNATURE_NL", signature_nl),
        form_fr_prefill_url_template=os.getenv("FORM_FR_PREFILL_URL_TEMPLATE", form_fr_prefill_url_template),
        form_nl_prefill_url_template=os.getenv("FORM_NL_PREFILL_URL_TEMPLATE", form_nl_prefill_url_template),
        calcom_api_key=os.getenv("CALCOM_API_KEY", calcom_api_key),
        calcom_base_url=os.getenv("CALCOM_BASE_URL", calcom_base_url),
        calcom_api_version=os.getenv("CALCOM_API_VERSION", calcom_api_version),
        calcom_username=os.getenv("CALCOM_USERNAME", calcom_username),
        calcom_private_visit_event_slug=os.getenv("CALCOM_PRIVATE_VISIT_EVENT_SLUG", calcom_private_visit_event_slug),
        calcom_open_house_event_slug=os.getenv("CALCOM_OPEN_HOUSE_EVENT_SLUG", calcom_open_house_event_slug),
        calcom_webhook_secret=os.getenv("CALCOM_WEBHOOK_SECRET", calcom_webhook_secret),
        webhook_base_url=os.getenv("WEBHOOK_BASE_URL", webhook_base_url),
        working_hours=os.getenv("WORKING_HOURS", working_hours),
    )
