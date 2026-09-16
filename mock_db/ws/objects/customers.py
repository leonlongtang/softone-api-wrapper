"""CUSTOMER object handlers: getData / setData / delData / selectorFields.

Mirrors the SoftOne CUSTOMER + CUSEXTRA tables (1:1 child).
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_BUSINESS_GENERIC, WS_INVALID_REQUEST, WS_NOT_FOUND
from .validators import delete_with_fk_guard


def _parse_locateinfo(locateinfo: str) -> dict[str, list[str]]:
    """Parse SoftOne's "TABLE:FIELD,FIELD;TABLE:FIELD" filter syntax."""
    wanted: dict[str, list[str]] = {}
    if not locateinfo:
        return wanted
    for part in locateinfo.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        t, fields = part.split(":", 1)
        wanted[t.strip().upper()] = [f.strip().upper() for f in fields.split(",") if f.strip()]
    return wanted


def get_customer(conn: sqlite3.Connection, key: Any, locateinfo: str = "") -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT trdr, code, name, afm, email, phone, address, balance, created_at
        FROM customers
        WHERE trdr = ?
        """,
        (int(key),),
    ).fetchone()
    if row is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")

    extra = conn.execute(
        "SELECT varchar01, varchar02 FROM cusextra WHERE trdr = ?",
        (int(key),),
    ).fetchone()

    wanted = _parse_locateinfo(locateinfo)

    customer_map = {
        "TRDR": row["trdr"],
        "CODE": row["code"],
        "NAME": row["name"],
        "AFM": row["afm"],
        "EMAIL": row["email"],
        "PHONE": row["phone"],
        "ADDRESS": row["address"],
        "BALANCE": row["balance"],
        "CREATED_AT": row["created_at"],
    }
    cusextra_map = {
        "VARCHAR01": extra["varchar01"] if extra else None,
        "VARCHAR02": extra["varchar02"] if extra else None,
    }

    def _filter(table: str, mapping: dict[str, Any]) -> dict[str, Any]:
        if not wanted:
            return {k: v for k, v in mapping.items() if v is not None}
        wf = wanted.get(table.upper())
        if not wf:
            return {}
        return {k: mapping.get(k) for k in wf}

    data: dict[str, Any] = {}
    cust_filtered = _filter("CUSTOMER", customer_map)
    if cust_filtered:
        data["CUSTOMER"] = [cust_filtered]
    extra_filtered = _filter("CUSEXTRA", cusextra_map)
    if extra_filtered:
        data["CUSEXTRA"] = [extra_filtered]

    return {"success": True, "readOnly": True, "data": data}


def set_customer(conn: sqlite3.Connection, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a customer (and optional CUSEXTRA child).

    Key handling matches SoftOne's tolerance for either numeric TRDR keys or
    reference keys: missing/empty/non-numeric => insert new TRDR.
    """
    if key is None or str(key).strip() == "":
        (mx,) = conn.execute("SELECT COALESCE(MAX(trdr), 0) + 1 AS next_id FROM customers").fetchone()
        target_trdr = int(mx)
    else:
        try:
            target_trdr = int(key)
        except ValueError:
            (mx,) = conn.execute("SELECT COALESCE(MAX(trdr), 0) + 1 AS next_id FROM customers").fetchone()
            target_trdr = int(mx)

    cust_rows = data.get("CUSTOMER") or []
    if not cust_rows:
        raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")
    cust = cust_rows[0]

    def g(field: str) -> Any:
        return cust.get(field)

    exists = conn.execute("SELECT 1 FROM customers WHERE trdr = ?", (target_trdr,)).fetchone() is not None
    if exists:
        conn.execute(
            """
            UPDATE customers
            SET code=COALESCE(?, code),
                name=COALESCE(?, name),
                afm=COALESCE(?, afm),
                email=COALESCE(?, email),
                phone=COALESCE(?, phone),
                address=COALESCE(?, address)
            WHERE trdr=?
            """,
            (
                g("CODE"), g("NAME"), g("AFM"), g("EMAIL"),
                g("PHONE") or g("PHONE01"), g("ADDRESS"),
                target_trdr,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO customers(trdr, code, name, afm, email, phone, address)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                target_trdr,
                g("CODE") or f"AUTO-{target_trdr}",
                g("NAME") or "",
                g("AFM"), g("EMAIL"),
                g("PHONE") or g("PHONE01"),
                g("ADDRESS"),
            ),
        )

    extra_rows = data.get("CUSEXTRA") or []
    if extra_rows:
        ex = extra_rows[0]
        ex_exists = conn.execute("SELECT 1 FROM cusextra WHERE trdr = ?", (target_trdr,)).fetchone() is not None
        if ex_exists:
            conn.execute(
                "UPDATE cusextra SET varchar01=COALESCE(?, varchar01), varchar02=COALESCE(?, varchar02) WHERE trdr=?",
                (ex.get("VARCHAR01"), ex.get("VARCHAR02"), target_trdr),
            )
        else:
            conn.execute(
                "INSERT INTO cusextra(trdr, varchar01, varchar02) VALUES (?,?,?)",
                (target_trdr, ex.get("VARCHAR01"), ex.get("VARCHAR02")),
            )

    conn.commit()
    return {"success": True, "id": str(target_trdr)}


def del_customer(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    cur = delete_with_fk_guard(
        conn, "DELETE FROM customers WHERE trdr = ?", (int(key),),
        what=f"customer {int(key)}",
    )
    if cur.rowcount == 0:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    conn.commit()
    return {"success": True}


def selector_lookup(conn: sqlite3.Connection, keyvalue: Any, resultfields: str) -> dict[str, Any]:
    """SoftOne's `selectorFields` lookup against TRDR.

    Only TRDR-by-customer is supported in the mock; everything else raises
    WS_BUSINESS_GENERIC to mirror the reference shape.
    """
    row = conn.execute(
        "SELECT trdr, code, name, afm FROM customers WHERE trdr = ?",
        (int(keyvalue),),
    ).fetchone()
    if row is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")

    wanted = [f.strip().upper() for f in resultfields.split(",") if f.strip()]
    mapping = {"TRDR": row["trdr"], "CODE": row["code"], "NAME": row["name"], "AFM": row["afm"]}
    result = {k: mapping.get(k) for k in wanted}
    return {"success": True, "totalcount": 1, "rows": [result]}


# Re-export so services/metadata.py doesn't have to know about
# WS_BUSINESS_GENERIC for the selectorFields path.
__all__ = [
    "del_customer", "get_customer", "selector_lookup", "set_customer",
    "WS_BUSINESS_GENERIC",
]
