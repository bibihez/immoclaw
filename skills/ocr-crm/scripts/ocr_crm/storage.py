from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import dump_json, ensure_dir, load_json, new_session_id, utcnow_iso


class SessionStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = ensure_dir(root_dir)
        self.sessions_dir = ensure_dir(self.root_dir / "sessions")
        self.assets_dir = ensure_dir(self.root_dir / "assets")
        self.cache_dir = ensure_dir(self.root_dir / "cache")

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id") or new_session_id()
        session = {
            "session_id": session_id,
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
            "status": "received",
            "assets": [],
            "events": [],
        }
        session.update(payload)
        self.save_session(session)
        return session

    def session_path(self, session_id: str) -> Path:
        return self.sessions_dir / "{session_id}.json".format(session_id=session_id)

    def load_session(self, session_id: str) -> dict[str, Any]:
        return load_json(self.session_path(session_id), {})

    def save_session(self, session: dict[str, Any]) -> None:
        session["updated_at"] = utcnow_iso()
        dump_json(self.session_path(session["session_id"]), session)

    def append_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        session.setdefault("events", []).append(
            {"type": event_type, "payload": payload, "created_at": utcnow_iso()}
        )
        self.save_session(session)
        return session

    def asset_dir(self, session_id: str) -> Path:
        return ensure_dir(self.assets_dir / session_id)

    def cache_path(self, name: str) -> Path:
        return self.cache_dir / "{name}.json".format(name=name)
