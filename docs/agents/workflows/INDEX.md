# Agent workflows (high-level)

Wiki-link target: `[[agent_workflows_index]]`

This folder documents **high-level agent workflows** (“business actions”) that should be achievable with **one tool call per step**.

These workflows sit *above* the CRUD-style domain tools and low-level SoftOne primitives.

## How to use this folder

- Start with `[[order_to_cash]]` for the main end-to-end flow.
- Use these docs when designing **agent-facing tools** (e.g. `create_order`) that internally orchestrate multiple CRUD calls.

## Conventions

- **One step = one business action**: avoid steps like “update ORDERITEMS table”.
- **Prefer agent-facing tools** when available; fall back to domain tools:
  - Domain tools: `customers_*`, `items_*`, `orders_*`, `orderitems_*`, `invoices_*`, `payments_*`
  - Low-level tools: `softone_getData`, `softone_setData`, `softone_delData`
- **Form-friendly inputs**: optional values are typically `""` meaning “omit”.

