# Agent → MCP translator policy (single-tool)

This document defines the **translator** behavior: converting natural language into **one deterministic MCP tool call** (or asking **one clarification question** when required).

## Output contract

The translator must produce **exactly one** of the following:

1) **A single MCP tool call** with a JSON object containing only the tool parameters.\n+2) **A single clarification question** if a safe tool call cannot be produced.

No multi-step plans, no speculative tool sequences, no hidden assumptions.

## Selection rules

- Prefer **workflow tools** when user intent is a business action.\n+  - For “place/create an order”: use `workflow_create_order`.\n+- Prefer **primitives** for lookup/verification.\n+  - For “who is this customer?”: `get_customer`.\n+  - For “do we have stock?”: `check_inventory`.\n+- If inputs are missing or ambiguous in a way that could change the write target, ask **one** question.\n+\n+## Required clarification triggers (ask, don’t guess)\n+\n+- **Customer ambiguous**: user gives a name that could match multiple customers and you cannot disambiguate deterministically.\n+- **Items ambiguous**: item name/code unclear or missing quantity.\n+- **Write intent unclear**: user asks something like “handle this order” without specifying action.\n+\n+## Determinism & safety\n+\n+- Never guess IDs.\n+  - If an ID/name/code is not provided, ask for it.\n+  - If provided but ambiguous, ask for a unique identifier.\n+- Keep tool calls **minimal** and **schema-valid**.\n+- Do not include `session_id` unless you already have it; otherwise ask the user to connect (or instruct the client to call `softone_connect_default`).\n+\n+## Tool preference table\n+\n+| User intent | Preferred tool |\n+|-----------|----------------|\n+| “Create/place an order” | `workflow_create_order` |\n+| “Get customer details” | `get_customer` |\n+| “Check item stock” | `check_inventory` |\n+| “Create invoice” | `create_invoice` (only if order is Confirmed) |\n+\n+## Examples\n+\n+### Example: order creation (good)\n+\n+User: \"Create an order for ACME: 2x IT-CHAIR, 1x IT-DESK\"\n+\n+Tool call:\n+\n+```json\n+{\n+  \"tool\": \"workflow_create_order\",\n+  \"args\": {\n+    \"session_id\": \"...\",\n+    \"customer\": \"ACME\",\n+    \"items\": [\n+      {\"item_name_or_id\": \"IT-CHAIR\", \"quantity\": 2},\n+      {\"item_name_or_id\": \"IT-DESK\", \"quantity\": 1}\n+    ],\n+    \"notes\": \"\",\n+    \"auto_approve\": \"if_under_threshold\"\n+  }\n+}\n+```\n+\n+### Example: needs clarification (good)\n+\n+User: \"Create an order for John\"\n+\n+Clarification question:\n+\n+\"Which customer should I use? Please provide customer id or exact code/name (e.g. `123` or `CUST-001`).\"\n+
