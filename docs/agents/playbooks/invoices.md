# Invoices playbook (agents)

This playbook shows invoice workflows using MCP tools.

## 0) Connect

```json
{}
```

Response:

```json
{ "ok": true, "data": { "session_id": "..." } }
```

## 1) Create an invoice

```json
{ "session_id": "...", "customer_id": 47, "order_id": "5001", "amount": "1225.0", "status": "unpaid" }
```

Notes:
- `order_id` is optional; leave empty (`""`) if it’s not tied to an order.
- `amount` is **form-friendly** (string): e.g. `"1225.0"`.

## 2) Fetch an invoice

```json
{ "session_id": "...", "key": 9001 }
```

## 3) Update an invoice

```json
{ "session_id": "...", "key": 9001, "status": "paid" }
```

## 4) Delete an invoice

```json
{ "session_id": "...", "key": 9001 }
```

