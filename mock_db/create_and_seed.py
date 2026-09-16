from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema.sql"
DEFAULT_DB_PATH = ROOT / "mock_softone.db"


@dataclass(frozen=True)
class SeedResult:
    db_path: Path
    account: dict
    temporary_client_id: str
    final_client_id: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_client_id() -> str:
    # SoftOne examples look like opaque tokens, sometimes URL-encoded.
    # We just need uniqueness + "token-like" appearance.
    return secrets.token_urlsafe(32)


def create_schema(conn: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)


def seed(conn: sqlite3.Connection) -> SeedResult:
    now = _utc_now()
    expires = now + timedelta(hours=8)

    # Web account from docs examples.
    account = {"username": "john", "password": "aitis", "appId": "2001"}
    cur = conn.execute(
        "INSERT INTO web_accounts(username, password, app_id) VALUES(?,?,?) RETURNING id",
        (account["username"], account["password"], account["appId"]),
    )
    (account_id,) = cur.fetchone()

    # The environment selection shown in docs.
    selection = {
        "COMPANY": "1000",
        "COMPANYNAME": "Demo Company SA",
        "BRANCH": "1000",
        "BRANCHNAME": "Athens",
        "MODULE": "0",
        "MODULENAME": "Center",
        "REFID": "1",
        "REFIDNAME": "Administrator",
    }
    conn.execute(
        """
        INSERT INTO login_selections(
          account_id, company, company_name, branch, branch_name, module, module_name, refid, refid_name
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            account_id,
            selection["COMPANY"],
            selection["COMPANYNAME"],
            selection["BRANCH"],
            selection["BRANCHNAME"],
            selection["MODULE"],
            selection["MODULENAME"],
            selection["REFID"],
            selection["REFIDNAME"],
        ),
    )

    tmp_client = _new_client_id()
    final_client = _new_client_id()

    conn.execute(
        """
        INSERT INTO sessions(client_id, account_id, is_final, created_at, expires_at)
        VALUES (?,?,?,?,?)
        """,
        (tmp_client, account_id, 0, now.isoformat(), expires.isoformat()),
    )

    conn.execute(
        """
        INSERT INTO sessions(client_id, account_id, is_final, created_at, expires_at, company, branch, module, refid)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            final_client,
            account_id,
            1,
            now.isoformat(),
            expires.isoformat(),
            selection["COMPANY"],
            selection["BRANCH"],
            selection["MODULE"],
            selection["REFID"],
        ),
    )

    # Business objects from docs example.
    conn.execute(
        "INSERT INTO business_objects(name, type, caption) VALUES (?,?,?)",
        ("CUSTOMER", "EditMaster", "Customers"),
    )

    # Object tables from docs example.
    conn.execute(
        """
        INSERT INTO object_tables(object_name, name, dbname, caption, filltype)
        VALUES (?,?,?,?,?)
        """,
        ("CUSTOMER", "CUSTOMER", "TRDR", "Customers", "SQL"),
    )
    conn.execute(
        """
        INSERT INTO object_tables(object_name, name, dbname, caption, filltype)
        VALUES (?,?,?,?,?)
        """,
        ("CUSTOMER", "CUSEXTRA", "TRDEXTRA", "Extra customer data", "SQL"),
    )

    # A subset of fields in the docs example (enough to power selectorFields-like queries).
    fields = [
        {
            "object": "CUSTOMER",
            "table": "CUSTOMER",
            "name": "TRDR",
            "fullname": "CUSTOMER.TRDR",
            "caption": "Customer",
            "size": "4",
            "type": "AutoInc",
            "edittype": "Simple",
            "readOnly": 1,
            "visible": 0,
            "required": 1,
            "calculated": 0,
        },
        {
            "object": "CUSTOMER",
            "table": "CUSTOMER",
            "name": "CODE",
            "fullname": "CUSTOMER.CODE",
            "caption": "Code",
            "size": "25",
            "type": "String",
            "edittype": "Simple",
            "readOnly": 0,
            "visible": 1,
            "required": 1,
            "calculated": 0,
        },
        {
            "object": "CUSTOMER",
            "table": "CUSTOMER",
            "name": "NAME",
            "fullname": "CUSTOMER.NAME",
            "caption": "Name",
            "size": "50",
            "type": "String",
            "edittype": "Simple",
            "readOnly": 0,
            "visible": 1,
            "required": 1,
            "calculated": 0,
        },
        {
            "object": "CUSTOMER",
            "table": "CUSTOMER",
            "name": "AFM",
            "fullname": "CUSTOMER.AFM",
            "caption": "AFM",
            "size": "15",
            "type": "String",
            "edittype": "Simple",
            "readOnly": 0,
            "visible": 1,
            "required": 0,
            "calculated": 0,
        },
    ]
    for f in fields:
        conn.execute(
            """
            INSERT INTO table_fields(
              object_name, table_name, name, alias, fullname, caption, size, type, edittype,
              defaultvalue, decimals, editor, readOnly, visible, required, calculated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f["object"],
                f["table"],
                f["name"],
                "",
                f["fullname"],
                f["caption"],
                f["size"],
                f["type"],
                f["edittype"],
                "",
                "",
                "",
                int(f["readOnly"]),
                int(f["visible"]),
                int(f["required"]),
                int(f["calculated"]),
            ),
        )

    # Customers — 5 rows. First 3 preserved from the selectorFields example
    # so existing docs/playbooks that cite TRDR=47 still work.
    conn.executemany(
        """
        INSERT INTO customers(
          trdr, code, name, afm, email, phone, address, balance, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                47,
                "100",
                "Soft One Technologies S.A.",
                "999863881",
                "johng@softone.gr",
                "+302109484797",
                "6 Poseidonos street, 17674 Kallithea",
                1000.0,
                now.isoformat(),
            ),
            (48, "101", "Holding SA", None, None, None, None, 0.0, now.isoformat()),
            (49, "102", "Demo Customer Ltd", "046156989", None, None, None, 0.0, now.isoformat()),
            (
                50,
                "103",
                "Aegean Electronics Ltd",
                "123456789",
                "sales@aegean-electronics.gr",
                "+302101112233",
                "12 Panepistimiou, 10679 Athens",
                250.0,
                now.isoformat(),
            ),
            (
                51,
                "104",
                "Mediterranean Foods SA",
                "987654321",
                "orders@medfoods.gr",
                "+302109998877",
                "45 Nikis, 54622 Thessaloniki",
                0.0,
                now.isoformat(),
            ),
        ],
    )

    # One cusextra row per customer so every TRDR has an entry.
    conn.executemany(
        "INSERT INTO cusextra(trdr, varchar01, varchar02) VALUES (?,?,?)",
        [
            (47, "Extra 1", "Extra 2"),
            (48, "VIP", None),
            (49, None, None),
            (50, "EU-VAT", "Region: Attica"),
            (51, "Wholesale", "Region: Macedonia"),
        ],
    )

    # Mock SQL script and rows (matches SqlData example fields).
    conn.execute("INSERT INTO sql_scripts(name, description) VALUES (?,?)", ("myItems", "Mock items list"))
    conn.executemany(
        "INSERT INTO sql_rows(script_name, mtrl, code, name, pricew, pricer) VALUES (?,?,?,?,?,?)",
        [
            ("myItems", "1191", "10001", 'Τηλεόραση LCD 32"', "900", "900"),
            ("myItems", "1192", "10002", "Laptop 14", "1200", "1200"),
            ("myItems", "1193", "10003", "Mouse", "20", "20"),
        ],
    )

    # Mock eInvoice record (matches response shape).
    conn.execute(
        """
        INSERT INTO invoices(
          doc_key, template, integritySignature, signature, uid, mark, authenticationCode
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            "47",
            "102",
            "5A4E71D37BE71D37BE3A71D37BEE1671D37BECB-2071D37BEADCC71D37BE3804C71D37BE001D6F0",
            "EL000000001-900000-3ACBA9271D37BE8BB4970675D71D37BEEDD226B7-DE8E6273CE9171D37BE5580171D37BEA",
            "A871D37BE12B338666D71D37BEFB71D37BE1FBB",
            402474254224724,
            "3876DGHJHJ8976NLINT9785TNLERGI785HLGINO8",
        ),
    )

    # Products (ITEMS)
    conn.execute("""
    INSERT INTO business_objects(name, type, caption)
    VALUES ('ITEM', 'EditMaster', 'Items')
    """)

    conn.execute("""
    INSERT INTO object_tables(object_name, name, dbname, caption, filltype)
    VALUES ('ITEM', 'ITEM', 'MTRL', 'Items', 'SQL')
    """)

    # Items — 5 rows. Stock + reserved values are consistent with the seeded
    # orders/invoices below (orders 5001-5004 are Confirmed + invoiced, so
    # their stock is already decremented; order 5005 is Draft, so its qty is
    # still sitting in `reserved`).
    conn.executemany("""
    INSERT INTO items(id, code, name, price, stock, reserved)
    VALUES (?,?,?,?,?,?)
    """, [
        (1001, "LAPTOP-14", "Laptop 14 inch", 1200, 14, 1),
        (1002, "MOUSE-01", "Wireless Mouse", 25, 46, 0),
        (1003, "KEYB-01", "Mechanical Keyboard", 80, 22, 0),
        (1004, "MON-27", '27" 4K Monitor', 450, 18, 1),
        (1005, "HDST-02", "USB Headset", 60, 37, 0),
    ])

    # Orders business object metadata (for discovery).
    conn.execute(
        "INSERT INTO business_objects(name, type, caption) VALUES (?,?,?)",
        ("ORDER", "EditMaster", "Orders"),
    )
    conn.execute(
        "INSERT INTO object_tables(object_name, name, dbname, caption, filltype) VALUES (?,?,?,?,?)",
        ("ORDER", "ORDER", "ORDERS", "Orders", "SQL"),
    )
    conn.execute(
        "INSERT INTO object_tables(object_name, name, dbname, caption, filltype) VALUES (?,?,?,?,?)",
        ("ORDER", "ORDERITEMS", "ORDER_ITEMS", "Order lines", "SQL"),
    )

    # Orders — 5 rows. Status values MUST match what `business/orders.py`
    # uses (`Draft` / `Confirmed`); the old seed used `pending`/`completed`
    # which would break `approve_order` and `create_invoice` flows.
    # 5001-5004 are Confirmed (so they can be invoiced below); 5005 stays
    # Draft so the demo has at least one order waiting for approval.
    conn.executemany("""
    INSERT INTO orders(id, customer_id, total, status)
    VALUES (?,?,?,?)
    """, [
        (5001, 47, 1225, "Confirmed"),
        (5002, 49, 80, "Confirmed"),
        (5003, 50, 1020, "Confirmed"),
        (5004, 48, 295, "Confirmed"),
        (5005, 51, 1650, "Draft"),
    ])

    # Order lines — totals match `orders.total` above.
    conn.executemany("""
    INSERT INTO order_items(order_id, product_id, quantity, price)
    VALUES (?,?,?,?)
    """, [
        # 5001: 1x laptop + 1x mouse = 1200 + 25 = 1225
        (5001, 1001, 1, 1200),
        (5001, 1002, 1, 25),
        # 5002: 1x keyboard = 80
        (5002, 1003, 1, 80),
        # 5003: 2x monitor + 2x headset = 900 + 120 = 1020
        (5003, 1004, 2, 450),
        (5003, 1005, 2, 60),
        # 5004: 3x mouse + 2x keyboard + 1x headset = 75 + 160 + 60 = 295
        (5004, 1002, 3, 25),
        (5004, 1003, 2, 80),
        (5004, 1005, 1, 60),
        # 5005 (Draft): 1x laptop + 1x monitor = 1200 + 450 = 1650
        (5005, 1001, 1, 1200),
        (5005, 1004, 1, 450),
    ])

    # Invoices (business-side — maps to `invoices_business`, not the
    # e-invoice `invoices` table seeded above). 5 rows covering every
    # payment status the mock_ws recomputes: paid, unpaid, partial.
    #   inv 1 → order 5001, fully paid (one full payment below)
    #   inv 2 → order 5002, unpaid (no payments)
    #   inv 3 → order 5003, partial (two partial payments below)
    #   inv 4 → order 5004, fully paid (two payments summing to total)
    #   inv 5 → customer 51, no order, unpaid (ad-hoc invoice)
    conn.executemany(
        """
        INSERT INTO invoices_business(id, customer_id, order_id, amount, status, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        [
            (1, 47, 5001, 1225.0, "paid", now.isoformat()),
            (2, 49, 5002, 80.0, "unpaid", now.isoformat()),
            (3, 50, 5003, 1020.0, "partial", now.isoformat()),
            (4, 48, 5004, 295.0, "paid", now.isoformat()),
            (5, 51, None, 500.0, "unpaid", now.isoformat()),
        ],
    )

    # Payments — 5 rows, consistent with the invoice statuses above.
    # Note: mock_ws recomputes invoice status from sum(payments), so the
    # sums here must actually match (`paid` → sum == amount, `partial` →
    # 0 < sum < amount, `unpaid` → sum == 0).
    conn.executemany(
        """
        INSERT INTO payments(id, invoice_id, amount, payment_date)
        VALUES (?,?,?,?)
        """,
        [
            (1, 1, 1225.0, now.isoformat()),              # inv 1 paid in full
            (2, 3, 500.0, now.isoformat()),               # inv 3 partial
            (3, 3, 300.0, now.isoformat()),               # inv 3 still partial (800/1020)
            (4, 4, 100.0, now.isoformat()),               # inv 4 partial
            (5, 4, 195.0, now.isoformat()),               # inv 4 now fully paid (295/295)
        ],
    )

    return SeedResult(
        db_path=DEFAULT_DB_PATH,
        account=account,
        temporary_client_id=tmp_client,
        final_client_id=final_client,
    )


def _print_quickstart(result: SeedResult) -> None:
    print(f"DB created at: {result.db_path}")
    print()
    print("Mock credentials (from softone.md examples):")
    print(json.dumps(result.account, indent=2))
    print()
    print("Mock clientIDs:")
    print(json.dumps({"temporary_clientID": result.temporary_client_id, "final_clientID": result.final_client_id}, indent=2))


def main() -> None:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        result = seed(conn)
        conn.commit()
    finally:
        conn.close()

    _print_quickstart(result)


if __name__ == "__main__":
    main()

