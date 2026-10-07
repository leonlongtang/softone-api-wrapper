# Order-to-cash workflow (agents)

This workflow covers the core business lifecycle:

Customer → Product/Item → Order → Invoice → Payment

## 0) Connect

```json
{}
```

Response:

```json
{ "ok": true, "data": { "session_id": "..." } }
```

## 1) Ensure customer exists

Preferred (agent tool, future):
- `create_customer(name, email="", phone="")`
- `get_customer(name_or_id)`

Current tools (today):
- Use `create_customer` to create
- Use `get_customer` to fetch by id

Example (create):

```json
{
  "session_id": "...",
  "code": "AG-001",
  "name": "Agent Customer",
  "email": "agent@example.com",
  "phone01": "+302100000000"
}
```

## 2) Ensure items exist

Preferred (agent tool, future):
- `create_product(name, price, stock)`
- `get_product(name_or_id)`

Current tools (today):
- Use `create_item` / `get_item`

Example (create item):

```json
{ "session_id": "...", "code": "NEW-ITEM", "name": "New Item", "price": 9.99, "stock": 10 }
```

## 3) Create an order

Preferred (agent tool, future):
- `create_order(customer_id, items)` where `items=[{product_id, quantity}]`

Current tools (today):
- Use `create_order` (supports initial lines)
- Or create header then manage lines with `orderitems_*`

Example (create order with lines):

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

## 4) Adjust order lines (if needed)

Current tools (today):
- Use `add_order_line` or `remove_order_line`

Example (add a line):

```json
{
  "session_id": "...",
  "order_id": 5003,
  "merge_if_exists": true,
  "line": { "product_id": 1002, "quantity": 1, "price": "" }
}
```

## 5) Create an invoice

Preferred (agent tool, future):
- `create_invoice(order_id)` (pull order total, set unpaid)

Current tools (today):
- Use `create_invoice` and provide `customer_id`, `order_id`, and `amount`

Example:

```json
{ "session_id": "...", "customer_id": 47, "order_id": "5003", "amount": "75.0", "status": "unpaid" }
```

## 6) Record a payment

Preferred (agent tool, future):
- `record_payment(invoice_id, amount)`

Current tools (today):
- Use `record_payment`

Example:

```json
{ "session_id": "...", "invoice_id": 9001, "amount": "50.0", "payment_date": "" }
```

Notes:
- In the mock, payments automatically update invoice status to `unpaid`/`partial`/`paid`.

