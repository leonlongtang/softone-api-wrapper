# Payments playbook (agents)

Wiki-link target: `[[playbook_payments]]`

This playbook shows payment workflows using MCP tools.

## 0) Connect

```json
{}
```

Response:

```json
{ "ok": true, "data": { "session_id": "..." } }
```

## 1) Record a payment for an invoice

```json
{ "session_id": "...", "invoice_id": 9001, "amount": "50.0", "payment_date": "" }
```

Notes:
- `amount` is **form-friendly** (string): e.g. `"50.0"`.
- In the mock, recording/deleting payments updates invoice `status` (`unpaid`/`partial`/`paid`) based on total paid vs invoice amount.

## 2) Fetch a payment

```json
{ "session_id": "...", "key": 7001 }
```

## 3) Update a payment

```json
{ "session_id": "...", "key": 7001, "amount": "75.0" }
```

## 4) Delete a payment

```json
{ "session_id": "...", "key": 7001 }
```

