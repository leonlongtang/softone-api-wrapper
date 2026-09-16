"""Backward-compatible facade for the SoftOne WS mock.

The implementation now lives under `mock_db.ws/` (router, services/, objects/,
errors, session). This module re-exports the public surface so existing
callers like `softone_wrapper/infrastructure/mock_gateway.py` keep working
without changes.

If you are writing new code, prefer importing from `mock_db.ws` directly.
"""
from __future__ import annotations

from .ws import WsError, authenticate, handle_request, login
from .ws.session import DEFAULT_DB_PATH

__all__ = [
    "DEFAULT_DB_PATH",
    "WsError",
    "authenticate",
    "handle_request",
    "login",
]
