# API wrapper (`softone_wrapper`)

This project wraps **SoftOne WS** calls behind a Python client with **stateful sessions**.

## Key files

- Wrapper: `softone_wrapper/client.py`
- Mock WS backend: `mock_db/mock_ws.py`
- Mock DB: `mock_db/mock_softone.db`

## Session model (important)

SoftOne WS uses `clientID` tokens. The wrapper hides that behind a `session_id`:

- `start_connection(...)` calls SoftOne `login`
- `complete_connection(...)` calls SoftOne `authenticate`
- After that, you call service methods using `session_id`

## Wrapper API surface (current)

### Connect

- `SoftOneClient.mock()` → mock gateway (SQLite)
- `SoftOneClient()` → real HTTP gateway

Auth flow:

- `start_connection(base_url, username, password, app_id, company?, branch?, module?, refid?)`
  - Returns either:
    - ready `session` (if selection was provided or SoftOne returned direct clientID), or
    - `{ temp_client_id, selections[] }` to complete auth
- `complete_connection(base_url, app_id, temp_client_id, selection)` → returns `SoftOneSession`

Minimal example:

```json
{
  "base_url": "mock://",
  "username": "john",
  "password": "aitis",
  "app_id": "2001"
}
```

### Discovery helpers (schema discovery)

- `getObjects(session_id)`
- `getObjectTables(session_id, OBJECT)`
- `getTableFields(session_id, OBJECT, TABLE)`

### Generic CRUD-style services (SoftOne WS primitives)

These work across ERP entities by changing `OBJECT` and the `data` tables.

- `getData(session_id, OBJECT, KEY, FORM="", LOCATEINFO="")`
- `setData(session_id, OBJECT, data, KEY=None, VERSION=None, LOCATEINFO="")`
- `delData(session_id, OBJECT, KEY, FORM="")`
- `calculate(session_id, OBJECT, KEY, data, LOCATEINFO="")`

Example `getData` call parameters:

```json
{
  "OBJECT": "CUSTOMER",
  "KEY": 47,
  "FORM": "",
  "LOCATEINFO": "CUSTOMER:CODE,NAME,AFM;CUSEXTRA:VARCHAR02"
}
```

Example `setData` insert parameters (KEY omitted/None):

```json
{
  "OBJECT": "CUSTOMER",
  "KEY": null,
  "data": {
    "CUSTOMER": [
      { "CODE": "NEW-001", "NAME": "New Customer", "AFM": "111111111" }
    ]
  }
}
```

## Mock limitations (current)

The mock implementation is meant for development/testing. Currently it supports:

- Auth (`login`, `authenticate`)
- `getObjects`, `getObjectTables`, `getTableFields`
- `getData`, `setData`, `delData`, `calculate` for `OBJECT="CUSTOMER"`
- `selectorFields`, `SqlData`, `eInvoice`

