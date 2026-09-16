# Manual workflow test checklist (V1 agent client)

Use this checklist to validate the workflow-first agent client against the mock DB.

## Setup
- Ensure `SOFTONE_*` env vars are set for mock mode as usual.
- Run the CLI orchestrator REPL:\n+  - `python apps/cli_orchestrator/run.py`\n+
## Tests

### 1) Connect (implicit)
- Enter: `Create an order for customer 47 with 1x item 1001`\n+- Expected:\n+  - Agent calls connect automatically if no session exists.\n+  - Agent prefers `workflow_create_order`.\n+\n+### 2) Inventory validation path\n+- Enter: `Create an order for customer 47 with 9999x item 1001`\n+- Expected:\n+  - Tool returns `ok:false` with an insufficient stock error.\n+  - Agent does not blindly retry; it asks what to do next (reduce qty / cancel).\n+\n+### 3) Order-to-cash workflow\n+- Enter: `Order to cash for customer 47: 1x item 1001`\n+- Expected:\n+  - Agent calls `workflow_order_to_cash`.\n+  - If order ends Draft, workflow returns a clear error that invoicing requires Confirmed (no auto-approve).\n+\n+### 4) Observability\n+- For workflow tool calls, inspect the returned envelope:\n+  - `meta.trace_id` exists\n+  - `meta.actions[]` includes resolve + create steps\n+
