from __future__ import annotations

from typing import Any


CAPABILITIES: dict[str, Any] = {
    "server": {
        "name": "softone-mcp",
        # Keep this manually updated if you want to surface versions to agents.
        "version": "dev",
    },
    "tools": [
        # Core / session
        {"name": "softone_connect_default", "mock_only": False, "side_effects": "writes"},
        {"name": "get_context", "mock_only": False, "side_effects": "none"},

        # Customers
        {"name": "create_customer", "mock_only": False, "side_effects": "writes"},
        {"name": "get_customer", "mock_only": False, "side_effects": "none"},
        {"name": "update_customer", "mock_only": False, "side_effects": "writes"},
        {"name": "delete_customer", "mock_only": False, "side_effects": "writes"},

        # Items / inventory
        {"name": "create_item", "mock_only": False, "side_effects": "writes"},
        {"name": "get_item", "mock_only": False, "side_effects": "none"},
        {"name": "update_item", "mock_only": False, "side_effects": "writes"},
        {"name": "delete_item", "mock_only": False, "side_effects": "writes"},
        {"name": "get_stock_balance", "mock_only": False, "side_effects": "none"},
        {"name": "inventory_adjustment", "mock_only": False, "side_effects": "writes"},

        # Sales / orders
        {"name": "create_order", "mock_only": False, "side_effects": "writes"},
        {"name": "approve_order", "mock_only": False, "side_effects": "writes"},
        {"name": "update_order", "mock_only": False, "side_effects": "writes"},
        {"name": "add_order_line", "mock_only": False, "side_effects": "writes"},
        {"name": "remove_order_line", "mock_only": False, "side_effects": "writes"},
        {"name": "get_order", "mock_only": False, "side_effects": "none"},
        {"name": "get_order_lines", "mock_only": False, "side_effects": "none"},
        {"name": "cancel_order", "mock_only": False, "side_effects": "writes"},

        # Invoices / AR
        {"name": "create_invoice", "mock_only": False, "side_effects": "writes"},
        {"name": "get_invoice", "mock_only": False, "side_effects": "none"},
        {"name": "get_unpaid_invoices", "mock_only": True, "side_effects": "none"},
        {"name": "list_invoices", "mock_only": True, "side_effects": "none"},

        # Payments
        {"name": "record_payment", "mock_only": False, "side_effects": "writes"},
        {"name": "list_invoice_payments", "mock_only": True, "side_effects": "none"},
        {"name": "get_payment", "mock_only": False, "side_effects": "none"},
        {"name": "refund_payment", "mock_only": False, "side_effects": "writes"},

        # Visibility helpers (mock-only today)
        {"name": "list_orders", "mock_only": True, "side_effects": "none"},
        {"name": "search_customers", "mock_only": True, "side_effects": "none"},
        {"name": "search_items", "mock_only": True, "side_effects": "none"},
    ],
    "vocabularies": {
        "orders.status": ["Draft", "Confirmed"],
        "invoices_business.status": ["unpaid", "partial", "paid"],
    },
    "rules": [
        {
            "name": "cancel_order",
            "summary": "Only Draft orders can be cancelled; MVP cancels by deletion.",
        },
        {
            "name": "inventory_adjustment",
            "summary": "Adjustment cannot make stock negative or below reserved.",
        },
        {
            "name": "invoice_per_order",
            "summary": "At most one business invoice per order_id.",
        },
    ],
}


GLOSSARY_MD = """\
## Glossary

- **customer_id**: The customer primary key used across tools. In the mock DB this maps to `customers.trdr`.
- **item_id**: The item primary key used across tools. In the mock DB this maps to `items.id`.
- **order_id**: The order primary key. In the mock DB this maps to `orders.id`.

## Two kinds of “invoice” in the mock DB

- **`invoices_business`**: The ERP business invoice used for accounts receivable (AR) and payments.\n\
  Tools like `create_invoice`, `get_invoice`, `list_invoices`, and `record_payment` operate on this concept.\n\
  Payment rows reference `payments.invoice_id -> invoices_business.id`.

- **`invoices`**: eInvoice / signature lookup records (MyData-style).\n\
  This is not your AR invoice; it stores signature blobs keyed by `(doc_key, template)`.

If you create an invoice from an order, it will appear in **`invoices_business`**.
"""


ORDER_TO_CASH_MD = """\
## Workflow: Order to Cash

Goal: **Customer → Order → Invoice → Payment**.

### Discover (visibility-first)
- Use `search_customers` to find a customer ID (mock-only).
- Use `search_items` to find item IDs (mock-only).
- Use `list_orders` / `get_order` to inspect existing orders (mock-only for list).
- Use `list_invoices` / `get_invoice` to inspect invoices (mock-only for list).

### Execute
1. `create_order(customer_id, items)`\n\
   - Reserves inventory (increases ITEM.RESERVED).\n\
   - Returns status `Draft` or auto-approved `Confirmed`.\n\
2. If status is `Draft`: `approve_order(order_id)`\n\
3. `create_invoice(order_id)`\n\
   - Requires order status `Confirmed`.\n\
   - Deducts stock and releases reservation.\n\
4. `record_payment(invoice_id, amount)`\n\
   - Updates invoice status in mock based on sum(payments).

### Verify
- `get_order`, `get_order_lines`
- `get_invoice`
- `list_invoice_payments` (mock-only)
"""


CONTRACTS: dict[str, Any] = {
    "customer": {
        "fields": [
            "code",
            "name",
            "afm",
            "email",
            "phone",
            "address",
            "balance",
            "created_at",
        ],
        "notes": [
            "Tools accept most optional fields as strings (empty string means omit).",
            "`code` can be auto-generated if omitted on create.",
        ],
    },
    "item": {
        "fields": ["code", "name", "price", "stock", "reserved", "created_at"],
        "notes": [
            "Stock semantics: available = stock - reserved (clamped at 0).",
        ],
    },
    "order": {
        "fields": ["customer_id", "status", "total", "created_at", "lines[]"],
        "status_vocabulary": ["Draft", "Confirmed"],
        "notes": [
            "Cancelling is Draft-only and deletes the order in the MVP.",
        ],
    },
    "invoice": {
        "fields": ["customer_id", "order_id", "amount", "status", "created_at"],
        "status_vocabulary": ["unpaid", "partial", "paid"],
        "notes": [
            "Business invoices live in `invoices_business` (AR).",
            "eInvoice signature records live in `invoices` and are a separate concept.",
        ],
    },
}


EXAMPLES_MD = """\
## Examples (minimal)

### Find a customer and create an order
1) `search_customers(q=\"Soft\")` → pick `customer_id`\n\
2) `search_items(q=\"Laptop\")` → pick `item_id`\n\
3) `create_order(customer_id=..., items=[{\"item_id\": 1001, \"quantity\": 1}])`

### List unpaid invoices and record a payment
1) `list_invoices(status=\"unpaid\")`\n\
2) `record_payment(invoice_id=..., amount=\"100.00\")`\n\
3) `list_invoice_payments(invoice_id=...)`
"""

