from __future__ import annotations

from typing import Any

from config import load_config
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError
from uuid import uuid4


def _default_meta() -> dict[str, Any]:
    # Keep this deterministic in *shape* (stable keys/types); values like trace_id are unique per call.
    return {"trace_id": str(uuid4()), "tool": "", "input_redacted": {}, "actions": []}


def ok(data: Any, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, "data": data, "meta": meta or _default_meta()}


def err(e: SoftOneError, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False, "error": e.to_dict(), "meta": meta or _default_meta()}


def build_client() -> SoftOneClient:
    cfg = load_config()
    return SoftOneClient.mock() if cfg.mock else SoftOneClient()

