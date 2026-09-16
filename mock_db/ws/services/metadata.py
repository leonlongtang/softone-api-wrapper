"""Discovery / metadata services.

Covers four services that all return SoftOne schema info, no per-row CRUD:
    getObjects        - list known business objects
    getObjectTables   - list child tables of a business object
    getTableFields    - list fields of a (object, table) pair
    selectorFields    - look up a single record by reference key

Each service signature is (payload, conn) -> response dict.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_BUSINESS_GENERIC
from ..objects.customers import selector_lookup


def get_objects_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT name, type, caption FROM business_objects ORDER BY name"
    ).fetchall()
    return {
        "success": True,
        "count": len(rows),
        "objects": [
            {"name": r["name"], "type": r["type"], "caption": r["caption"]}
            for r in rows
        ],
    }


def get_object_tables_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    obj = str(payload.get("OBJECT", ""))
    rows = conn.execute(
        """
        SELECT name, dbname, caption, filltype
        FROM object_tables
        WHERE object_name = ?
        ORDER BY id
        """,
        (obj,),
    ).fetchall()
    return {
        "success": True,
        "count": len(rows),
        "tables": [
            {
                "name": r["name"],
                "dbname": r["dbname"],
                "caption": r["caption"],
                "filltype": r["filltype"],
            }
            for r in rows
        ],
    }


def get_table_fields_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    obj = str(payload.get("OBJECT", ""))
    table = str(payload.get("TABLE", ""))
    rows = conn.execute(
        """
        SELECT name, alias, fullname, caption, size, type, edittype, defaultvalue, decimals, editor,
               readOnly, visible, required, calculated
        FROM table_fields
        WHERE object_name = ? AND table_name = ?
        ORDER BY id
        """,
        (obj, table),
    ).fetchall()
    return {
        "success": True,
        "count": len(rows),
        "fields": [
            {
                "name": r["name"],
                "alias": r["alias"],
                "fullname": r["fullname"],
                "caption": r["caption"],
                "size": r["size"],
                "type": r["type"],
                "edittype": r["edittype"],
                "defaultvalue": r["defaultvalue"],
                "decimals": r["decimals"],
                "editor": r["editor"],
                "readOnly": bool(r["readOnly"]),
                "visible": bool(r["visible"]),
                "required": bool(r["required"]),
                "calculated": bool(r["calculated"]),
            }
            for r in rows
        ],
    }


def selector_fields_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    """Mock supports CUSTOMER.TRDR only. Anything else returns the generic
    "Business error" SoftOne uses for unsupported lookups."""
    tablename = str(payload.get("TABLENAME", "")).upper()
    keyname = str(payload.get("KEYNAME", "")).upper()
    keyvalue = payload.get("KEYVALUE")
    resultfields = str(payload.get("RESULTFIELDS", ""))

    if tablename != "CUSTOMER" or keyname != "TRDR":
        raise WsError(WS_BUSINESS_GENERIC, "Business error")

    return selector_lookup(conn, keyvalue, resultfields)
