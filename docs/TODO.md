# TODO

- [x] Implement the rest of the customer MCP tools (and docs):
  - MCP tools: `customers_get`, `customers_update`, `customers_delete` (and optionally `customers_list/search`)
  - Update docs:
    - `docs/mcp/tools_catalog.md`
    - `docs/agents/playbooks/customer.md`
  - Keep tools agent-friendly (clear names/descriptions, JSON examples, form-friendly optional strings where helpful)

- [x] Implement CRUD MCP tools for Orders (and docs):
  - Create a new domain tools file: `softone_mcp/tools/orders.py`
  - MCP tools: `orders_create`, `orders_get`, `orders_update`, `orders_delete`
  - Update docs:
    - `docs/mcp/tools_catalog.md` (add order tools + JSON examples)
    - `docs/agents/playbooks/order.md` (new playbook)
  - Mock scope: align to `mock_db/schema.sql` tables (`orders`, `order_items`, `items`) and existing mock CRUD behavior

- [x] Implement OrderItems MCP tools (line-level order editing) (and docs):
  - MCP tools (suggested):
    - `orderitems_replace_lines` (set all lines for an order)
    - `orderitems_add_line` (append one line)
    - `orderitems_remove_line` (remove a product from an order)
  - Update docs:
    - `docs/mcp/tools_catalog.md` (add tool entries + JSON examples)
    - `docs/agents/playbooks/order.md` (use these instead of low-level `softone_setData` where possible)
  - Mock behavior should keep totals correct (`SUM(quantity * price)`)

- [x] Implement Items MCP tools (and docs):
  - Create a new domain tools file: `softone_mcp/tools/items.py`
  - MCP tools (suggested):
    - `items_create`, `items_get`, `items_update`, `items_delete`
    - optionally `items_list` / `items_search`
  - Update docs:
    - `docs/mcp/tools_catalog.md` (add item tools + JSON examples)
    - `docs/agents/playbooks/items.md` (new playbook)
  - Mock scope: align to `mock_db/schema.sql` table `items` (code/name/price/stock)

- [x] Implement Payments MCP tools (and docs):
  - Create a new domain tools file: `softone_mcp/tools/payments.py`
  - MCP tools (suggested):
    - `payments_create`, `payments_get`, `payments_update`, `payments_delete`
    - optionally `payments_list` / `payments_search` (by customer/order/date)
  - Update docs:
    - `docs/mcp/tools_catalog.md` (add payment tools + JSON examples)
    - `docs/agents/playbooks/payments.md` (new playbook)
  - Mock scope: align to `mock_db/schema.sql` table `payments`

- [x] Implement Invoices MCP tools (and docs):
  - Create a new domain tools file: `softone_mcp/tools/invoices.py`
  - MCP tools (suggested):
    - `invoices_create`, `invoices_get`, `invoices_update`, `invoices_delete`
    - optionally `invoices_list` / `invoices_search` (by customer/order/date/status)
  - Update docs:
    - `docs/mcp/tools_catalog.md` (add invoice tools + JSON examples)
    - `docs/agents/playbooks/invoices.md` (new playbook)
  - Mock scope: align to `mock_db/schema.sql` table `invoices_business`

- [x] Add agent-facing documentation for high-level “business action” tools:
  - Goal: agents call one tool per business action (no table/CRUD thinking)
  - Add docs:
    - `docs/agents/workflows/INDEX.md` (entry point + conventions)
    - `docs/agents/workflows/order_to_cash.md` (customer → product → order → invoice → payment)
  - Update:
    - `docs/INDEX.md` to link the new workflows docs
    - `docs/mcp/tools_catalog.md` with a new section “Agent tools (business actions)”

- [ ] Implement high-level agent tools (V1) on top of existing CRUD tools:
  - [ ] Customers:
    - `create_customer(name, email="", phone="")`
    - `get_customer(name_or_id)`
    - Optional: `update_customer_info(customer_id, **fields)`, `list_customers(filter="")`
  - [ ] Products/Items:
    - `create_product(name, price, stock)`
    - `get_product(name_or_id)`
    - Optional: `update_product_stock(product_id, new_stock)`, `list_products(filter="")`
  - [ ] Orders:
    - `create_order(customer_id, items)` where `items=[{product_id, quantity}]`
      - Internal: validate item existence/stock (optional rule), create order, add/replace lines, ensure total correct
    - `get_order(order_id)`
    - Optional: `cancel_order(order_id)`, `list_customer_orders(customer_id)`
  - [ ] Invoices:
    - `create_invoice(order_id)` (pull order total, set unpaid)
    - `get_unpaid_invoices(customer_id="")`
    - Optional: `mark_invoice_paid(invoice_id)`, `list_invoices(filter="")`
  - [ ] Payments:
    - `record_payment(invoice_id, amount)` (update invoice status to partial/paid)
    - Optional: `get_payments(invoice_id="", customer_id="")`, `refund_payment(payment_id)`
  - [ ] Docs:
    - Add examples for each tool in `docs/agents/workflows/` and `docs/mcp/tools_catalog.md`