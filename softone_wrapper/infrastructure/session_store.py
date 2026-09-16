from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..domain.errors import NotAuthenticated, SessionExpired
from ..domain.models import SoftOneSession


@dataclass(frozen=True)
class _SessionRecord:
    base_url: str
    app_id: str
    client_id: str
    expires_at: Optional[datetime]
    company: Optional[str]
    branch: Optional[str]
    module: Optional[str]
    refid: Optional[str]


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, _SessionRecord] = {}

    def new_session_id(self) -> str:
        return secrets.token_urlsafe(24)

    def put(
        self,
        *,
        session_id: str,
        base_url: str,
        app_id: str,
        client_id: str,
        expires_at: Optional[datetime] = None,
        company: Optional[str] = None,
        branch: Optional[str] = None,
        module: Optional[str] = None,
        refid: Optional[str] = None,
    ) -> None:
        self._sessions[session_id] = _SessionRecord(
            base_url=base_url,
            app_id=app_id,
            client_id=client_id,
            expires_at=expires_at,
            company=company,
            branch=branch,
            module=module,
            refid=refid,
        )

    def get(self, session_id: str) -> SoftOneSession:
        rec = self._sessions.get(session_id)
        if rec is None:
            raise NotAuthenticated(-1, "Invalid request. Please login first")

        if rec.expires_at is not None:
            now = datetime.now(timezone.utc)
            exp = rec.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                raise SessionExpired(-101, "Invalid Request, session has expired!")

        return SoftOneSession(
            session_id=session_id,
            base_url=rec.base_url,
            app_id=rec.app_id,
            client_id=rec.client_id,
            expires_at=rec.expires_at,
            company=rec.company,
            branch=rec.branch,
            module=rec.module,
            refid=rec.refid,
        )

