from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SoftOneError(Exception):
    """
    Domain-level error for SoftOne WS failures.

    `code` corresponds to SoftOne's error codes when available (see softone.md).
    `details` may include raw response fragments for debugging.
    """

    code: int
    message: str
    details: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details or {}}


class InvalidCredentials(SoftOneError):
    pass


class SessionExpired(SoftOneError):
    pass


class NotAuthenticated(SoftOneError):
    pass


class InvalidServiceCall(SoftOneError):
    pass


class InvalidRequest(SoftOneError):
    pass

