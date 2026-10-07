# MCP overview (`softone_mcp`)

The MCP server provides **tools** for agents to operate SoftOne ERP via the Python wrapper.

## Code locations

- MCP server root: `softone_mcp/server.py`
- Domain tools: `softone_mcp/tools/` (`customers.py`, `items.py`, `orders.py`, `invoices.py`, `payments.py`, `connect.py`)
- Tool / envelope audit: [`docs/mcp/tool_audit.md`](./tool_audit.md)
- Full tool list and JSON examples: [`docs/mcp/tools_catalog.md`](./tools_catalog.md)

## Design: two tool layers

### 1) Raw SoftOne services (Python only)

The wrapper (`softone_wrapper.SoftOneClient`) exposes SoftOne WS services directly (`getData`, `setData`, `delData`, …).
They are deliberately **not** MCP tools: agents only see the domain tools below, plus `softone_connect_default`.

### 2) Domain tools (agent-friendly)

These encode a business intent and hide SoftOne payload structure. See the generated tool table in [`tools_catalog.md`](./tools_catalog.md) for the current tool names (`create_customer`, `get_order_lines`, `list_invoice_payments`, …).

## Configuration

`softone_connect_default` uses `.env` values loaded by `config.load_config()`:

- `SOFTONE_MOCK=true|false`
- `SOFTONE_BASE_URL=.../s1services`
- `SOFTONE_USERNAME=...`
- `SOFTONE_PASSWORD=...`
- `SOFTONE_APP_ID=...`

## Tool response envelope

Every tool returns one of:

- Success:

```json
{ "ok": true, "data": { "...": "..." } }
```

- Error:

```json
{
  "ok": false,
  "error": { "code": -101, "message": "Invalid Request, session has expired!", "details": { } }
}
```

## Inspector UI notes

The MCP Inspector “form” UI does not always render optional/union fields well.

Best practice:

- For agent usage: always send JSON payloads (Inspector “Switch to JSON”).
- For human testing in form mode: keep inputs simple (`str` with `""` defaults) where possible.
- For `create_customer`, optional fields are implemented as empty strings (form-friendly).

## Agent prompt policy

The department agents in `agent_platform/specs.py` follow the baseline policy documented in:
- [`docs/agents/agent_prompt_policy.md`](../agents/agent_prompt_policy.md)

