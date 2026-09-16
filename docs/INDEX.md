# SoftOne Wrapper + MCP (Obsidian Vault)

This `docs/` folder is an Obsidian vault documenting how the **API wrapper** and **MCP server** fit together, so future agents can use the tools correctly.

## Start here

- [[api_wrapper]] (Python wrapper surface, parameters, examples)
- [[mcp_overview]] (how MCP is structured around the wrapper)
- [[mcp_tools_catalog]] (tool list + JSON examples)
- [[playbook_customer]] (end-to-end customer workflows for agents)
- [[playbook_order]] (end-to-end order workflows for agents)
- [[playbook_items]] (end-to-end item workflows for agents)
- [[playbook_payments]] (end-to-end payment workflows for agents)
- [[playbook_invoices]] (end-to-end invoice workflows for agents)
- [[agent_workflows_index]] (high-level business workflows for agents)
- [[prompt_service_generator]] (prompt to generate new domain tools + docs entries)

## Key conventions

- **SoftOne terms**: `OBJECT`, `KEY`, `data`, `LOCATEINFO` (match SoftOne WS)
- **MCP tool envelope**:
  - Success: `{ "ok": true, "data": <softone_response> }`
  - Error: `{ "ok": false, "error": { "code": int, "message": str, "details": {...} } }`

