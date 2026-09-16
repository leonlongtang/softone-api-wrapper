"""SoftOne WS API emulator.

Layered as:
    router          -> dispatches by `service` field
    services/       -> per-service request/response shaping
    objects/        -> per-OBJECT logic (validation, CRUD, normalization)
    session, errors -> shared infrastructure

The mock simulates SoftOne's *API surface*; it does NOT replicate ERP
internals. Company-policy logic (auto-approve thresholds, payment terms,
invoice generation rules) lives in `softone_mcp/business/`, not here.
"""
from __future__ import annotations

from .errors import WsError
from .router import handle_request
from .session import authenticate, login

__all__ = ["WsError", "authenticate", "handle_request", "login"]
