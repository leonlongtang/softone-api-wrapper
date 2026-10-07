"""Router: dispatches a `service`-tagged payload to the right service handler.

Pattern: SERVICES is a dict mapping service name to a callable. Each
authenticated service callable has the signature `(payload, conn) -> dict`.
The unauthenticated `login` and `authenticate` services are special-cased
because they manage the session lifecycle themselves and don't need a
pre-validated session.

Adding a new service is a one-line entry in `SERVICES` plus the handler
file.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable

from .errors import WS_INVALID_CALL, WsError
from .services.calculate import calculate_service
from .services.del_data import del_data_service
from .services.einvoice import einvoice_service
from .services.get_data import get_data_service
from .services.metadata import (
    get_object_tables_service,
    get_objects_service,
    get_table_fields_service,
    selector_fields_service,
)
from .services.set_data import set_data_service
from .services.sql_data import sql_data_service
from .session import (
    DEFAULT_DB_PATH,
    _connect,
    _require_session,
    authenticate,
    login,
)

# Type alias: every authenticated service handler takes (payload, conn).
ServiceHandler = Callable[[dict[str, Any], sqlite3.Connection], dict[str, Any]]


# All services that REQUIRE a session. login/authenticate are routed
# separately because they create the session.
SERVICES: dict[str, ServiceHandler] = {
    "getObjects": get_objects_service,
    "getObjectTables": get_object_tables_service,
    "getTableFields": get_table_fields_service,
    "selectorFields": selector_fields_service,
    "SqlData": sql_data_service,
    "getData": get_data_service,
    "setData": set_data_service,
    "delData": del_data_service,
    "calculate": calculate_service,
    "eInvoice": einvoice_service,
}


def handle_request(
    payload: dict[str, Any], *, db_path: Path = DEFAULT_DB_PATH
) -> dict[str, Any]:
    """Top-level entrypoint. Takes a SoftOne-shaped payload (with `service`)
    and returns the matching response dict. Raises `WsError` for any
    SoftOne-style failure -- the caller (e.g., the mock gateway) is
    responsible for converting that into the wire envelope.
    """
    service = payload.get("service")

    # Pre-session services -- they manage the session lifecycle themselves.
    if service == "login":
        return login(
            username=str(payload.get("username", "")),
            password=str(payload.get("password", "")),
            appId=str(payload.get("appId", "")),
            COMPANY=payload.get("COMPANY"),
            BRANCH=payload.get("BRANCH"),
            MODULE=payload.get("MODULE"),
            REFID=payload.get("REFID"),
            db_path=db_path,
        )
    if service == "authenticate":
        return authenticate(
            clientID=str(payload.get("clientID", "")),
            COMPANY=str(payload.get("COMPANY", "")),
            BRANCH=str(payload.get("BRANCH", "")),
            MODULE=str(payload.get("MODULE", "")),
            REFID=str(payload.get("REFID", "")),
            db_path=db_path,
        )

    handler = SERVICES.get(str(service or ""))
    if handler is None:
        raise WsError(WS_INVALID_CALL, "Invalid Web Service call.")

    # All services below require a valid (non-expired) session.
    conn = _connect(db_path)
    try:
        client_id = str(payload.get("clientID", ""))
        _require_session(conn, client_id)
        return handler(payload, conn)
    finally:
        conn.close()
