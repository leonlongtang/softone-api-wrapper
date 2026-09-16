# Prompt: generate a new MCP domain tool

Wiki-link target: `[[prompt_service_generator]]`

Use this prompt when you want to add a new **agent-friendly** tool (e.g. `customers_update`, `orders_create`) on top of the low-level `softone_*` tools.

## Prompt

You are a backend engineer working on this repository.

### Context

- The low-level SoftOne tools already exist (see `docs/mcp/tools_catalog.md`).
- Domain tools must be registered as `@mcp.tool(name=..., description=...)`.
- Keep code organized by domain under `softone_mcp/tools/`.
- Tools return:
  - success: `{ "ok": true, "data": ... }`
  - error: `{ "ok": false, "error": { "code": int, "message": str, "details": {...} } }`
- Prefer **form-friendly** inputs for Inspector where it doesn’t harm agent usage:
  - Use `str` with default `""` for optional strings, and omit them in payload when empty.
- Always document new tools in `docs/mcp/tools_catalog.md` and add a playbook example if appropriate.

### Task

Generate a new MCP tool named: `<TOOL_NAME>`

1) Define a Pydantic `BaseModel` input schema with good `Field(..., description=...)`.
2) Implement the tool function that calls into the wrapper (`SoftOneClient`) using existing low-level primitives.
3) Register it in the appropriate domain module under `softone_mcp/tools/`.
4) Update docs:
   - Add an entry to `docs/mcp/tools_catalog.md` (name, inputs, example JSON).
   - If workflow-like, add/update a playbook under `docs/agents/playbooks/`.

### Output

- Provide the code changes and the updated docs entries.
- Keep changes minimal and consistent with existing repository style.
