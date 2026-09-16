# Customer playbook (agents)

Wiki-link target: `[[playbook_customer]]`

This playbook shows end-to-end customer workflows using MCP tools.

## 0) Connect

Call `softone_connect_default` (no inputs). It returns a `session_id`.

```json
{}
```

Response:

```json
{ "ok": true, "data": { "session_id": "..." } }
```

## 1) Create a customer (agent-friendly)

Use `customers_create` for most agent workflows.

```json
{
  "session_id": "...",
  "code": "AG-001",
  "name": "Agent Customer",
  "afm": "123456789",
  "email": "agent@example.com",
  "phone01": "+302100000000",
  "address": "1 AI Street",
  "remarks": "Created by playbook"
}
```

Expected success shape:

```json
{ "ok": true, "data": { "success": true, "id": "50" } }
```

## 2) Verify (agent-friendly)

Use `customers_get` after create.

```json
{
  "session_id": "...",
  "key": 50,
  "locateinfo": "CUSTOMER:CODE,NAME,AFM"
}
```

## 3) Update a customer (low-level)

Prefer `customers_update` for simple patches:

```json
{
  "session_id": "...",
  "key": 50,
  "remarks": "Updated via customers_update"
}
```

If you need to update complex tables/lines, fall back to `softone_setData`.

## 4) Delete a customer

Prefer `customers_delete`:

```json
{
  "session_id": "...",
  "key": 50
}
```

## Notes

- In the mock backend, only `OBJECT=\"CUSTOMER\"` is supported for CRUD tools.
- For agent use, prefer JSON payloads (Inspector “Switch to JSON”).
