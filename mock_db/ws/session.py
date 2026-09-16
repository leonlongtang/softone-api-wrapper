"""Session + auth: connection management, login, authenticate.

Owns the DB-path constants because the entire WS layer talks to one SQLite
file and `_connect` is the only place that opens it.
"""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .errors import (
    WsError,
    WS_BAD_CREDENTIALS,
    WS_NO_SESSION,
    WS_SESSION_EXPIRED,
)


# Path constants. The seed script writes the DB next to mock_db/, so __file__
# must walk up two levels (out of `ws/` then out of `mock_db/`'s subpackage).
_PKG_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = _PKG_ROOT / "mock_softone.db"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_client_id() -> str:
    # SoftOne examples look like opaque tokens, sometimes URL-encoded. We just
    # need uniqueness + token-shaped output.
    return secrets.token_urlsafe(32)


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _require_session(conn: sqlite3.Connection, client_id: str) -> sqlite3.Row:
    """Return the session row; raise WsError if missing or expired.

    Used by every authenticated service handler at the top of router dispatch.
    """
    row = conn.execute(
        "SELECT account_id, expires_at, is_final, company, branch, module, refid "
        "FROM sessions WHERE client_id = ?",
        (client_id,),
    ).fetchone()
    if row is None:
        raise WsError(WS_NO_SESSION, "Invalid request. Please login first")

    now = _utc_now()
    exp = datetime.fromisoformat(row["expires_at"]).astimezone(timezone.utc)
    if exp < now:
        raise WsError(WS_SESSION_EXPIRED, "Invalid Request, session has expired!")

    return row


# ---------------------------------------------------------------------------
# Auth services
# ---------------------------------------------------------------------------

def login(
    *,
    username: str,
    password: str,
    appId: str,
    # Optional "skip authenticate" params -- if all four are passed we go
    # straight to a final clientID without a separate authenticate() round-trip.
    COMPANY: Optional[str] = None,
    BRANCH: Optional[str] = None,
    MODULE: Optional[str] = None,
    REFID: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
    session_hours: int = 8,
) -> dict[str, Any]:
    """Mimics the SoftOne WS `login` JSON response shape from softone.md.

    - If COMPANY/BRANCH/MODULE/REFID are NOT provided: returns temporary clientID + objs selections.
    - If they ARE provided (and match a seeded selection): returns final clientID only.
    """
    now = _utc_now()
    expires = now + timedelta(hours=session_hours)

    conn = _connect(db_path)
    try:
        account_row = conn.execute(
            """
            SELECT id
            FROM web_accounts
            WHERE username = ? AND password = ? AND app_id = ?
            """,
            (username, password, appId),
        ).fetchone()
        if account_row is None:
            # Reference table: -2 = authenticate fails due to invalid creds.
            # The `login` row is less explicit, but this is the closest match.
            raise WsError(WS_BAD_CREDENTIALS, "Authenticate fails due to invalid credentials.")

        account_id = int(account_row["id"])

        # If the caller provided a complete selection, validate it and return
        # the final clientID directly (skip the authenticate step).
        if all(v is not None for v in (COMPANY, BRANCH, MODULE, REFID)):
            sel = conn.execute(
                """
                SELECT *
                FROM login_selections
                WHERE account_id = ?
                  AND company = ?
                  AND branch = ?
                  AND module = ?
                  AND refid = ?
                """,
                (account_id, COMPANY, BRANCH, MODULE, REFID),
            ).fetchone()
            if sel is None:
                raise WsError(WS_BAD_CREDENTIALS, "Authenticate fails due to invalid credentials.")

            final_client_id = _new_client_id()
            conn.execute(
                """
                INSERT INTO sessions(client_id, account_id, is_final, created_at, expires_at, company, branch, module, refid)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    final_client_id, account_id, 1,
                    now.isoformat(), expires.isoformat(),
                    COMPANY, BRANCH, MODULE, REFID,
                ),
            )
            conn.commit()
            return {"success": True, "clientID": final_client_id}

        # Otherwise: temporary clientID + the available selection list.
        tmp_client_id = _new_client_id()
        conn.execute(
            """
            INSERT INTO sessions(client_id, account_id, is_final, created_at, expires_at)
            VALUES (?,?,?,?,?)
            """,
            (tmp_client_id, account_id, 0, now.isoformat(), expires.isoformat()),
        )
        sels = conn.execute(
            """
            SELECT company, company_name, branch, branch_name, module, module_name, refid, refid_name
            FROM login_selections
            WHERE account_id = ?
            ORDER BY id
            """,
            (account_id,),
        ).fetchall()
        objs = [
            {
                "COMPANY": s["company"],
                "COMPANYNAME": s["company_name"],
                "BRANCH": s["branch"],
                "BRANCHNAME": s["branch_name"],
                "MODULE": s["module"],
                "MODULENAME": s["module_name"],
                "REFID": s["refid"],
                "REFIDNAME": s["refid_name"],
            }
            for s in sels
        ]
        conn.commit()
        return {"success": True, "clientID": tmp_client_id, "objs": objs}
    finally:
        conn.close()


def authenticate(
    *,
    clientID: str,
    COMPANY: str,
    BRANCH: str,
    MODULE: str,
    REFID: str,
    db_path: Path = DEFAULT_DB_PATH,
    session_hours: int = 8,
) -> dict[str, Any]:
    """Mimics the SoftOne WS `authenticate` response shape from softone.md."""
    now = _utc_now()
    expires = now + timedelta(hours=session_hours)

    conn = _connect(db_path)
    try:
        tmp = conn.execute(
            "SELECT account_id, expires_at, is_final FROM sessions WHERE client_id = ?",
            (clientID,),
        ).fetchone()
        if tmp is None:
            raise WsError(WS_NO_SESSION, "Invalid request. Please login first")
        if int(tmp["is_final"]) == 1:
            # If a final clientID is reused here, just confirm it.
            return {"success": True, "clientID": clientID}

        if datetime.fromisoformat(tmp["expires_at"]).astimezone(timezone.utc) < now:
            raise WsError(WS_SESSION_EXPIRED, "Invalid Request, session has expired!")

        account_id = int(tmp["account_id"])
        sel = conn.execute(
            """
            SELECT 1
            FROM login_selections
            WHERE account_id = ?
              AND company = ?
              AND branch = ?
              AND module = ?
              AND refid = ?
            """,
            (account_id, COMPANY, BRANCH, MODULE, REFID),
        ).fetchone()
        if sel is None:
            raise WsError(WS_BAD_CREDENTIALS, "Authenticate fails due to invalid credentials.")

        final_client_id = _new_client_id()
        conn.execute(
            """
            INSERT INTO sessions(client_id, account_id, is_final, created_at, expires_at, company, branch, module, refid)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                final_client_id, account_id, 1,
                now.isoformat(), expires.isoformat(),
                COMPANY, BRANCH, MODULE, REFID,
            ),
        )
        conn.commit()
        return {"success": True, "clientID": final_client_id}
    finally:
        conn.close()
