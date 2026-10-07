# Items playbook (agents)

This playbook shows end-to-end item workflows using MCP tools.

## 0) Connect

```json
{}
```

Response:

```json
{ "ok": true, "data": { "session_id": "..." } }
```

## 1) Create an item

```json
{ "session_id": "...", "code": "NEW-ITEM", "name": "New Item", "price": 9.99, "stock": 10 }
```

Expected success shape:

```json
{ "ok": true, "data": { "success": true, "id": "1004" } }
```

## 2) Fetch an item

```json
{ "session_id": "...", "key": 1004 }
```

## 3) Update an item

```json
{ "session_id": "...", "key": 1004, "price": "12.5", "stock": "7" }
```

## 4) Delete an item

```json
{ "session_id": "...", "key": 1004 }
```

## Notes

- In the mock backend, items are backed by the `items` table.

## Search

- Use `search_items` to find an item by code/name before acting on it.

