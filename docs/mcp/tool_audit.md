# MCP domain tools — stack audit

Wiki-link target: `[[mcp_tool_audit]]`

This document records how domain MCP tools are structured and whether they are suitable for agent use without further refactors.

## Layer contract

- **Tools** ([`softone_mcp/tools/`](../../softone_mcp/tools/)) own the `{ "ok": true, "data" }` / `{ "ok": false, "error" }` envelope ([`softone_mcp/deps.py`](../../softone_mcp/deps.py)).
- **Business** ([`softone_mcp/business/`](../../softone_mcp/business/)) implements use cases, returns raw dicts, raises domain exceptions or `ValueError` for rule violations.
- **Internal** ([`softone_mcp/internal/`](../../softone_mcp/internal/)) maps to SoftOne WS payloads; lets `SoftOneError` propagate.

## Existing tools (readiness)

| Tool | Envelope | Domain errors | Notes |
|------|----------|-----------------|-------|
| `softone_connect_default` | Yes | Maps start failures | No `session_id` input. |
| `create_customer` / `get_customer` | Yes | `ValueError`, `CustomerNotFoundError`, `SoftOneError` | `get_customer` resolves id or name/code (mock). |
| `create_item` / `get_item` | Yes | Same pattern as customers | |
| `create_order` / `approve_order` / `get_order` | Yes | Stock, status, not-found mapped | |
| `create_invoice` / `get_unpaid_invoices` / `get_invoice` | Yes | Order/invoice/terms errors mapped | `payment_terms` validated in BL. |
| `record_payment` / `get_payment` / `refund_payment` | Yes | Balance / paid / not-found mapped | |

## Update / delete customer and item (BL + tools)

[`update_customer_bl`](../../softone_mcp/business/customers.py) / [`delete_customer_bl`](../../softone_mcp/business/customers.py) (and item equivalents) are thin wrappers over SoftOne `setData` / `delData`. MCP tools **preflight** with `get_*_bl` so missing entities surface as `CustomerNotFoundError` / `ItemNotFoundError` like other reads. SoftOne-level failures (e.g. FK delete blocked, code 2003) still propagate as `SoftOneError` in the envelope.

## New read helpers

- `get_order_lines` — order must exist (`OrderNotFoundError`), then normalized lines.
- `list_invoice_payments` — invoice must exist (`InvoiceNotFoundError`), then payments for that invoice.

## Related docs

- Full parameter list and JSON examples: [`tools_catalog.md`](./tools_catalog.md).
- MCP overview: [`overview.md`](./overview.md).
