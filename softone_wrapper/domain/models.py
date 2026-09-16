from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LoginSelection:
    COMPANY: str
    COMPANYNAME: str
    BRANCH: str
    BRANCHNAME: str
    MODULE: str
    MODULENAME: str
    REFID: str
    REFIDNAME: str


@dataclass(frozen=True)
class SoftOneSession:
    """
    Wrapper session abstraction.

    - `session_id`: local identifier used by the wrapper.
    - `client_id`: SoftOne WS `clientID` (final).
    """

    session_id: str
    base_url: str
    app_id: str
    client_id: str
    expires_at: Optional[datetime] = None

    company: Optional[str] = None
    branch: Optional[str] = None
    module: Optional[str] = None
    refid: Optional[str] = None

