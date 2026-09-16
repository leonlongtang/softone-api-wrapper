# MCP tools catalog

Wiki-link target: `[[mcp_tools_catalog]]`

This catalog lists tool **names**, **inputs**, and **example JSON calls**. Tool names must match code exactly.

## Response envelope (all MCP business tools)

All MCP tools in `softone_mcp` return a stable envelope:

- Success: `{ "ok": true, "data": <payload>, "meta": <trace> }`
- Error: `{ "ok": false, "error": <softone_error_dict>, "meta": <trace> }`

The `meta` block is designed for observability/trust:
- `meta.trace_id`: unique id for this tool call
- `meta.tool`: tool name
- `meta.input_redacted`: sanitized inputs (no secrets)
- `meta.actions[]`: ordered action events (`name`, `status`, `detail`, `started_at`, `ended_at`)

## Connection

### `softone_connect_default`

Connects using `.env` (`SOFTONE_*`) and returns a `session_id` to use in all other tools.

Example call:

```json
{}
```

Example success response:

```json
{
  "ok": true,
  "data": { "session_id": "..." },
  "meta": {
    "trace_id": "...",
    "tool": "softone_connect_default",
    "input_redacted": {},
    "actions": []
  }
}
```

## Domain business tools (current `softone_mcp`)

Registered from [`softone_mcp/server.py`](../../softone_mcp/server.py). All business tools take `session_id` first (except connect). Responses use the `{ok, data, meta}` / `{ok, error, meta}` envelope. Stack notes: [`tool_audit.md`](./tool_audit.md).

| Tool | Parameters (after `session_id`) |
|------|----------------------------------|
| `create_customer` | `name`, `email=""`, `phone=""` |
| `get_customer` | `name_or_id`, `locateinfo=""` |
| `update_customer` | `name_or_id`, `name=""`, `email=""`, `phone=""`, `afm=""`, `address=""`, `balance=""` |
| `delete_customer` | `name_or_id` |
| `create_item` | `name`, `price=""`, `stock=""` |
| `get_item` | `name_or_id`, `locateinfo=""` |
| `update_item` | `name_or_id`, `name=""`, `price=""`, `stock=""` |
| `delete_item` | `name_or_id` |
| `check_inventory` | `item_name_or_id` |
| `create_order` | `customer_id`, `items` (array of `{item_id, quantity}`), `notes=""` |
| `workflow_create_order` | `customer`, `items` (array of `{item_name_or_id, quantity}`), `notes=\"\"`, `auto_approve=\"if_under_threshold\"` |
| `approve_order` | `order_id` |
| `get_order` | `order_id` |
| `get_order_lines` | `order_id` |
| `create_invoice` | `order_id`, `payment_terms="net_30"` |
| `get_unpaid_invoices` | `customer_id=""` |
| `get_invoice` | `invoice_id` |
| `record_payment` | `invoice_id`, `amount`, `payment_date=""` |
| `list_invoice_payments` | `invoice_id` |
| `get_payment` | `payment_id` |
| `refund_payment` | `payment_id` |

### `check_inventory`

Check inventory for a single item (stock/reserved/available). Accepts item id or name/code (mock resolves name/code).

```json
{ "session_id": "...", "item_name_or_id": "IT-DESK" }
```

### `workflow_create_order`

Preferred “place an order” tool. Resolves customer + items deterministically, validates stock, reserves inventory, creates the order, and applies `auto_approve`.

```json
{
  "session_id": "...",
  "customer": "ACME",
  "items": [
    { "item_name_or_id": "IT-CHAIR", "quantity": 2 },
    { "item_name_or_id": "IT-DESK", "quantity": 1 }
  ],
  "notes": "",
  "auto_approve": "if_under_threshold"
}
```

### `update_customer`

Patch fields on an existing customer. `name_or_id` is a numeric id or a name/code string (mock resolves lookups). Empty optional strings are skipped.

```json
{
  "session_id": "...",
  "name_or_id": "47",
  "email": "billing@example.com",
  "phone": ""
}
```

### `delete_customer`

Deletes by id or resolvable name/code. Fails with SoftOne error `2003` if the customer still has dependent rows (e.g. orders).

```json
{ "session_id": "...", "name_or_id": "52" }
```

### `update_item`

Same pattern as `update_customer` for catalog items (`name`, `price`, `stock` patches).

### `delete_item`

Deletes by id or resolvable name/code. Fails with `2003` if the item is referenced on order lines.

### `get_order_lines`

Returns `{ "order_id": int, "lines": [{ "item_id", "quantity", "unit_price" }, ...] }`. Fails with not found if the order id does not exist.

```json
{ "session_id": "...", "order_id": 5001 }
```

### `list_invoice_payments`

Returns `{ "invoice_id": int, "payments": [{ "id", "invoice_id", "amount", "payment_date" }, ...] }`. Fails if the invoice does not exist.

```json
{ "session_id": "...", "invoice_id": 1 }
```

## Low-level tools (generic SoftOne primitives)

### `softone_getObjects`

Inputs:
- `session_id` (string)

Example:

```json
{ "session_id": "..." }
```

### `softone_getObjectTables`

Inputs:
- `session_id` (string)
- `OBJECT` (string) e.g. `"CUSTOMER"`

Example:

```json
{ "session_id": "...", "OBJECT": "CUSTOMER" }
```

### `softone_getTableFields`

Inputs:
- `session_id` (string)
- `OBJECT` (string)
- `TABLE` (string)

Example:

```json
{ "session_id": "...", "OBJECT": "CUSTOMER", "TABLE": "CUSTOMER" }
```

### `softone_getData`

Inputs:
- `session_id` (string)
- `OBJECT` (string)
- `KEY` (int|string)
- `FORM` (string, optional, usually `""`)
- `LOCATEINFO` (string, optional)

Example:

```json
{
  "session_id": "...",
  "OBJECT": "CUSTOMER",
  "KEY": 47,
  "FORM": "",
  "LOCATEINFO": "CUSTOMER:CODE,NAME,AFM;CUSEXTRA:VARCHAR02"
}
```

### `softone_setData`

Inputs:
- `session_id` (string)
- `OBJECT` (string)
- `data` (object: `{TABLE: [row, ...], ...}` where each row is `{field: scalar}`)
- `KEY` (string, optional; omit to insert)
- `VERSION` (int, optional)
- `LOCATEINFO` (string, optional)

Insert example (omit `KEY`):

```json
{
  "session_id": "...",
  "OBJECT": "CUSTOMER",
  "data": {
    "CUSTOMER": [
      { "CODE": "NEW-001", "NAME": "New Customer", "AFM": "111111111" }
    ]
  }
}
```

Update example:

```json
{
  "session_id": "...",
  "OBJECT": "CUSTOMER",
  "KEY": "47",
  "data": {
    "CUSTOMER": [
      { "CODE": "100", "NAME": "Soft One Technologies S.A.", "REMARKS": "Updated" }
    ]
  }
}
```

### `softone_delData`

Inputs:
- `session_id` (string)
- `OBJECT` (string)
- `KEY` (int|string)
- `FORM` (string, optional)

Example:

```json
{ "session_id": "...", "OBJECT": "CUSTOMER", "KEY": 50, "FORM": "" }
```

### `softone_calculate`

Inputs:
- `session_id` (string)
- `OBJECT` (string)
- `KEY` (int|string)
- `data` (same shape as `softone_setData`)
- `LOCATEINFO` (string, optional)

Example:

```json
{
  "session_id": "...",
  "OBJECT": "CUSTOMER",
  "KEY": 47,
  "LOCATEINFO": "CUSTOMER:CODE,NAME,AFM",
  "data": {
    "CUSTOMER": [
      { "CODE": "100", "NAME": "Soft One Technologies S.A.", "AFM": "999863881" }
    ]
  }
}
```

## Domain tools (agent-friendly)

## Agent tools (business actions) (planned)

These are the **high-level tools** your agents should prefer once implemented. Each tool represents one business action and may orchestrate multiple domain/CRUD calls internally.

Planned V1 (names/inputs will be finalized when implemented):

- `create_customer(name, email="", phone="")`
- `get_customer(name_or_id)`
- `create_product(name, price, stock)`
- `get_product(name_or_id)`
- `create_order(customer_id, items)` where `items=[{product_id, quantity}]`
- `get_order(order_id)`
- `create_invoice(order_id)`
- `get_unpaid_invoices(customer_id="")`
- `record_payment(invoice_id, amount)`

For now, use the **Domain tools** below (`customers_*`, `items_*`, `orders_*`, `orderitems_*`, `invoices_*`, `payments_*`) to achieve the same workflows. See `[[agent_workflows_index]]` → `[[order_to_cash]]`.

### `customers_create`

Creates a new CUSTOMER record.

Inputs:
- `session_id` (string)
- `code` (string)
- `name` (string)
- `afm` (string, optional, leave empty to omit)
- `email` (string, optional, leave empty to omit)
- `phone01` (string, optional, leave empty to omit)
- `address` (string, optional, leave empty to omit)
- `remarks` (string, optional, leave empty to omit)

Example:

```json
{
  "session_id": "...",
  "code": "AG-001",
  "name": "Agent Customer",
  "afm": "123456789",
  "email": "agent@example.com",
  "phone01": "+302100000000",
  "address": "1 AI Street",
  "remarks": "Created by agent"
}
```

### `customers_get`

Fetches a customer by id (TRDR) using `softone_getData`.

Inputs:
- `session_id` (string)
- `key` (int)
- `locateinfo` (string, optional)

Example:

```json
{
  "session_id": "...",
  "key": 47,
  "locateinfo": "CUSTOMER:CODE,NAME,AFM"
}
```

### `customers_update`

Updates a customer by id (TRDR). Empty strings are treated as “omit”.

Inputs:
- `session_id` (string)
- `key` (int)
- `code` (string, optional, leave empty to omit)
- `name` (string, optional, leave empty to omit)
- `afm` (string, optional, leave empty to omit)
- `email` (string, optional, leave empty to omit)
- `phone01` (string, optional, leave empty to omit)
- `address` (string, optional, leave empty to omit)
- `remarks` (string, optional, leave empty to omit)

Example:

```json
{
  "session_id": "...",
  "key": 47,
  "email": "new@example.com",
  "remarks": "Updated by agent"
}
```

### `customers_delete`

Deletes a customer by id (TRDR) using `softone_delData`.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 50 }
```

### `orders_create`

Creates a new order (mock-backed, uses `OBJECT="ORDER"`).

Data model (mock + recommended agent mental model):

- **Header table**: `ORDER`
  - fields used by the mock: `CUSTOMER_ID`, `STATUS`
- **Lines table**: `ORDERITEMS`
  - each line maps to `PRODUCT_ID`, `QUANTITY`, `PRICE` (optional; defaults from item price in mock)

Inputs:
- `session_id` (string)
- `customer_id` (int)
- `status` (string, optional, leave empty to omit)
- `lines` (array, optional): `[{ "product_id": int, "quantity": int, "price": float(optional) }]`

Example:

```json
{
  "session_id": "...",
  "customer_id": 47,
  "status": "pending",
  "lines": [
    { "product_id": 1001, "quantity": 1 },
    { "product_id": 1002, "quantity": 2, "price": 25.0 }
  ]
}
```

### `orders_get`

Fetches an order by id.

Returns:
- `data.ORDER[0]`: order header (`ID`, `CUSTOMER_ID`, `STATUS`, `TOTAL`, `CREATED_AT`)
- `data.ORDERITEMS[]`: order lines
  - the mock enriches each line with `PRODUCT_CODE` and `PRODUCT_NAME` for agent convenience

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 5001 }
```

### `orders_update`

Updates an order by id (currently supports `status`).

Line semantics:

- `orders_update` does **not** edit lines (only header fields like `status`).
- To edit lines, use the low-level tool `softone_setData` with `OBJECT="ORDER"` and include `ORDERITEMS`.
  - In the mock, if `ORDERITEMS` is provided, it **replaces all existing lines** for the order.

Inputs:
- `session_id` (string)
- `key` (int)
- `status` (string, optional, leave empty to omit)

Example:

```json
{ "session_id": "...", "key": 5001, "status": "completed" }
```

### `orders_delete`

Deletes an order by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 5001 }
```

### `orderitems_replace_lines`

Replaces **all** order lines for an order id (writes `OBJECT="ORDER"` with `ORDERITEMS`).

Inputs:
- `session_id` (string)
- `order_id` (int)
- `lines` (array): `[{ "product_id": int, "quantity": int, "price": string(optional, leave empty to omit) }]`

Example:

```json
{
  "session_id": "...",
  "order_id": 5001,
  "lines": [
    { "product_id": 1001, "quantity": 1 },
    { "product_id": 1002, "quantity": 2, "price": "25.0" }
  ]
}
```

### `orderitems_add_line`

Appends a line to an order (optionally merges quantity if product already exists).

Inputs:
- `session_id` (string)
- `order_id` (int)
- `merge_if_exists` (bool, optional, default true)
- `line` (object): `{ "product_id": int, "quantity": int, "price": string(optional, leave empty to omit) }`

Example:

```json
{
  "session_id": "...",
  "order_id": 5001,
  "merge_if_exists": true,
  "line": { "product_id": 1002, "quantity": 1 }
}
```

### `orderitems_remove_line`

Removes a product line from an order.

Inputs:
- `session_id` (string)
- `order_id` (int)
- `product_id` (int)

Example:

```json
{ "session_id": "...", "order_id": 5001, "product_id": 1001 }
```

### `items_create`

Creates a new item (mock-backed, uses `OBJECT="ITEM"`).

Inputs:
- `session_id` (string)
- `code` (string)
- `name` (string)
- `price` (float)
- `stock` (int, optional, default 0)

Example:

```json
{ "session_id": "...", "code": "NEW-ITEM", "name": "New Item", "price": 9.99, "stock": 10 }
```

### `items_get`

Fetches an item by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 1001 }
```

### `items_update`

Updates an item by id.

Inputs:
- `session_id` (string)
- `key` (int)
- `code` (string, optional, leave empty to omit)
- `name` (string, optional, leave empty to omit)
- `price` (string, optional, leave empty to omit; parsed as number)
- `stock` (string, optional, leave empty to omit; parsed as integer)

Example:

```json
{ "session_id": "...", "key": 1001, "price": "1299.0", "stock": "8" }
```

### `items_delete`

Deletes an item by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 1003 }
```

### `payments_create`

Records a payment for an invoice (mock-backed, uses `OBJECT="PAYMENT"`).

Inputs:
- `session_id` (string)
- `invoice_id` (int)
- `amount` (string; parsed as number)
- `payment_date` (string, optional; leave empty to omit)

Example:

```json
{ "session_id": "...", "invoice_id": 9001, "amount": "50.0", "payment_date": "" }
```

### `payments_get`

Fetches a payment by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 7001 }
```

### `payments_update`

Updates a payment by id. Empty strings are treated as “omit”.

Inputs:
- `session_id` (string)
- `key` (int)
- `amount` (string, optional; leave empty to omit; parsed as number)
- `payment_date` (string, optional; leave empty to omit)

Example:

```json
{ "session_id": "...", "key": 7001, "amount": "75.0" }
```

### `payments_delete`

Deletes a payment by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 7001 }
```

### `invoices_create`

Creates an invoice (mock-backed, uses `OBJECT="INVOICE"`).

Inputs:
- `session_id` (string)
- `customer_id` (int)
- `order_id` (string, optional; leave empty to omit; parsed as int)
- `amount` (string; parsed as number)
- `status` (string, optional; leave empty to use default)

Example:

```json
{ "session_id": "...", "customer_id": 47, "order_id": "5001", "amount": "1225.0", "status": "unpaid" }
```

### `invoices_get`

Fetches an invoice by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 9001 }
```

### `invoices_update`

Updates an invoice by id. Empty strings are treated as “omit”.

Inputs:
- `session_id` (string)
- `key` (int)
- `customer_id` (string, optional; leave empty to omit; parsed as int)
- `order_id` (string, optional; leave empty to omit; parsed as int)
- `amount` (string, optional; leave empty to omit; parsed as number)
- `status` (string, optional; leave empty to omit)

Example:

```json
{ "session_id": "...", "key": 9001, "status": "paid" }
```

### `invoices_delete`

Deletes an invoice by id.

Inputs:
- `session_id` (string)
- `key` (int)

Example:

```json
{ "session_id": "...", "key": 9001 }
```

## Low-level order CRUD (when you need line control)

If agents need full control of lines, use low-level tools:

- `softone_getData` with `OBJECT="ORDER"`
- `softone_setData` with `OBJECT="ORDER"`
- `softone_delData` with `OBJECT="ORDER"`

### Example: replace lines with `softone_setData`

```json
{
  "session_id": "...",
  "OBJECT": "ORDER",
  "KEY": "5001",
  "data": {
    "ORDER": [
      { "STATUS": "pending" }
    ],
    "ORDERITEMS": [
      { "PRODUCT_ID": 1001, "QUANTITY": 1 },
      { "PRODUCT_ID": 1002, "QUANTITY": 2, "PRICE": 25.0 }
    ]
  }
}
```
