"""WsError + error code constants used across the mock WS.

Code conventions:
    Negative codes mirror the SoftOne reference table (-1, -2, -9, -101, -12).
    Positive codes 2xxx are mock-specific but follow SoftOne's positive-code shape
    (2001 is the documented "data does not exist" code; 2003 / 2010 are mock-only).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# --- SoftOne reference table codes --------------------------------------
WS_INVALID_REQUEST = -9            # generic "Invalid Request"
WS_NO_SESSION = -1                 # caller did not log in
WS_BAD_CREDENTIALS = -2            # authenticate / login failed
WS_SESSION_EXPIRED = -101          # session has expired
WS_INVALID_CALL = -12              # unknown service routed
WS_BUSINESS_GENERIC = 0            # generic "business error" (used by docs)

# --- Mock-only codes ----------------------------------------------------
WS_NOT_FOUND = 2001                # documented "Data does not exist"
WS_FK_BLOCKED = 2003               # delete blocked because rows reference this
WS_BUSINESS_RULE = 2010            # business rule violation: missing FK target,
                                   # illegal status transition, insufficient
                                   # stock, duplicate invoice, etc.


@dataclass(frozen=True)
class WsError(Exception):
    """SoftOne-style structured error.

    Carries a `code` (mirrors SoftOne reference table where possible) and a
    human-readable `message`. The router converts these into the standard
    `{"success": False, "error": {...}}` response envelope.
    """

    code: int
    message: str

    def to_response(self) -> dict[str, Any]:
        # SoftOne responses always include "success"; the public reference
        # doesn't pin down the exact error envelope, so this keeps it minimal
        # but useful for debugging.
        return {"success": False, "error": {"code": self.code, "message": self.message}}
