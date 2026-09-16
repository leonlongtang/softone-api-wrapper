# Order playbook (agents)

Wiki-link target: `[[playbook_order]]`

This playbook shows end-to-end order workflows using MCP tools.

## 0) Connect

```json
{}
```

Response:

```json
{ "ok": true, "data": { "session_id": "..." } }
```

## 1) Create an order

Orders are modeled as:

- **Header**: `ORDER` table
- **Lines**: `ORDERITEMS` table

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

Expected success shape:

```json
{ "ok": true, "data": { "success": true, "id": "5003" } }
```

## 2) Fetch an order

```json
{ "session_id": "...", "key": 5003 }
```

## 3) Update an order header (status)

```json
{ "session_id": "...", "key": 5003, "status": "completed" }
```

## 3b) Edit order lines (agent-friendly)

Prefer these tools over low-level `softone_setData` for line edits:

### Replace all lines

```json
{
  "session_id": "...",
  "order_id": 5003,
  "lines": [
    { "product_id": 1001, "quantity": 1 },
    { "product_id": 1002, "quantity": 3, "price": "25.0" }
  ]
}
```

### Add a line (or merge quantity if product already exists)

```json
{
  "session_id": "...",
  "order_id": 5003,
  "merge_if_exists": true,
  "line": { "product_id": 1002, "quantity": 1 }
}
```

### Remove a product line

```json
{ "session_id": "...", "order_id": 5003, "product_id": 1001 }
```

Notes:
- In the mock, line changes keep totals correct (`SUM(quantity * price)`).
- `price` is **form-friendly**: leave empty (`""`) to omit and let the mock default from the item.

## 4) Delete an order

```json
{ "session_id": "...", "key": 5003 }
```

## Notes

- In the mock backend, orders are backed by `orders` and `order_items` tables.
- Order totals are computed as `SUM(quantity * price)` in the mock.

