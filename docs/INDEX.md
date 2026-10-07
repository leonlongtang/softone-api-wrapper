# SoftOne Agent Platform docs

These docs describe how the **API wrapper** and **MCP server** fit together, so future agents can use the tools correctly.

## Start here

- [SoftOne WS reference](softone_ws_reference.md) (raw JSON services)
- [api wrapper](api/api_wrapper.md) (Python wrapper surface, parameters, examples)
- [mcp overview](mcp/overview.md) (how MCP is structured around the wrapper)
- [mcp tools catalog](mcp/tools_catalog.md) (generated from the live server: every tool + params)
- [playbook customer](agents/playbooks/customer.md) (end-to-end customer workflows for agents)
- [playbook order](agents/playbooks/order.md) (end-to-end order workflows for agents)
- [playbook items](agents/playbooks/items.md) (end-to-end item workflows for agents)
- [playbook payments](agents/playbooks/payments.md) (end-to-end payment workflows for agents)
- [playbook invoices](agents/playbooks/invoices.md) (end-to-end invoice workflows for agents)
- [agent workflows index](agents/workflows/INDEX.md) (high-level business workflows for agents)

## Key conventions

- **SoftOne terms**: `OBJECT`, `KEY`, `data`, `LOCATEINFO` (match SoftOne WS)
- **MCP tool envelope**:
  - Success: `{ "ok": true, "data": <softone_response> }`
  - Error: `{ "ok": false, "error": { "code": int, "message": str, "details": {...} } }`

