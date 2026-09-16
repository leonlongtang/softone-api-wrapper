from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActionEvent:
    name: str
    status: str = "ok"  # "ok" | "error"
    detail: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=_now_iso)
    ended_at: str | None = None

    def end_ok(self, *, detail: dict[str, Any] | None = None) -> None:
        if detail:
            self.detail.update(detail)
        self.status = "ok"
        self.ended_at = _now_iso()

    def end_error(self, *, detail: dict[str, Any] | None = None) -> None:
        if detail:
            self.detail.update(detail)
        self.status = "error"
        self.ended_at = _now_iso()


@dataclass
class Trace:
    tool: str
    input_redacted: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    actions: list[ActionEvent] = field(default_factory=list)

    @contextmanager
    def action(self, name: str, *, detail: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        ev = ActionEvent(name=name, detail=(detail or {}))
        self.actions.append(ev)
        ctx: dict[str, Any] = {}
        try:
            yield ctx
        except Exception:
            ev.end_error(detail={"ctx": ctx})
            raise
        else:
            ev.end_ok(detail={"ctx": ctx})

    def meta(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "tool": self.tool,
            "input_redacted": self.input_redacted,
            "actions": [
                {
                    "name": ev.name,
                    "status": ev.status,
                    "detail": ev.detail,
                    "started_at": ev.started_at,
                    "ended_at": ev.ended_at,
                }
                for ev in self.actions
            ],
        }
