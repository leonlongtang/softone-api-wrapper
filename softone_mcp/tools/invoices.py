"""
Agent-facing invoice tools.

Layer contract:
    - This layer OWNS the `{ok, data}` / `{ok, error}` envelope.
    - Wrap every successful business-layer result with ok(...).
    - Catch SoftOneError and domain exceptions, and return err(...).

Tool inputs are intentionally FLAT (no nested `inp: SomeModel` wrapper):
LLMs generate tool-calls far more reliably against flat JSON schemas than
against nested ones. Validation/descriptions are preserved via
`Annotated[type, Field(...)]`.
"""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from softone_mcp.business.constants import SOFTONE_BAD_INPUT_CODE, SOFTONE_NOT_FOUND_CODE
from softone_mcp.business.invoices import (
    create_invoice_bl,
    get_invoice_bl,
    list_invoices_bl,
    get_unpaid_invoices_bl,
)
from softone_mcp.business.exceptions import (
    InvalidOrderStatusError,
    InvalidPaymentTermsError,
    InvoiceNotFoundError,
    OrderNotFoundError,
)
from softone_mcp.deps import err, ok
from softone_mcp.observability import Trace
from softone_mcp.internal.adapters.inventory import SoftOneInventoryService
from softone_mcp.internal.adapters.repositories import (
    SoftOneInvoiceRepository,
    SoftOneOrderRepository,
)
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError


# ---------------------------------------------------------------------------
# MCP tool registrations
# ---------------------------------------------------------------------------

def register_invoice_tools(mcp: FastMCP, client: SoftOneClient) -> None:

    @mcp.tool(name="create_invoice", description=(
        "Generate an invoice from a Confirmed order. "
        "Calculates due date from payment terms, deducts stock from inventory. "
        "The order must be in Confirmed status — use approve_order first if needed."
    ))
    def create_invoice_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        order_id: Annotated[
            int, Field(description="ID of a Confirmed order to invoice")
        ],
        payment_terms: Annotated[
            str,
            Field(description="Payment terms: 'due_on_receipt', 'net_30', 'net_60', 'net_90'"),
        ] = "net_30",
    ) -> dict[str, Any]:
        orders_repo = SoftOneOrderRepository(client, session_id)
        invoices_repo = SoftOneInvoiceRepository(client, session_id)
        inventory = SoftOneInventoryService(client, session_id)
        try:
            data = create_invoice_bl(
                orders_repo,
                invoices_repo,
                inventory,
                order_id=order_id,
                payment_terms=payment_terms,
            )
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}
            ))
        except InvalidOrderStatusError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(e),
                {
                    "order_id": e.order_id,
                    "current_status": e.current,
                    "expected_status": e.expected,
                    "hint": (
                        "Order must be Confirmed before invoicing. "
                        "Call approve_order first."
                    ),
                },
            ))
        except InvalidPaymentTermsError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE, str(e), {"terms": e.terms}
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="workflow_order_to_cash",
        description=(
            "Workflow: create order (with reservations) and then create an invoice if the "
            "resulting order is Confirmed. This workflow will NOT auto-approve Draft orders "
            "during invoicing; use auto_approve on the order step or call approve_order explicitly."
        ),
    )
    def workflow_order_to_cash_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        customer: Annotated[
            str,
            Field(description="Customer id or name/code (mock supports name/code lookup)."),
        ],
        items: Annotated[
            list[dict[str, Any]],
            Field(description="Order lines: [{\"item_name_or_id\": str, \"quantity\": int}, ...]."),
        ],
        notes: Annotated[str, Field(description="Optional order notes")] = "",
        auto_approve: Annotated[
            str,
            Field(description="Auto-approve policy for the order step: never | if_under_threshold | always."),
        ] = "if_under_threshold",
        payment_terms: Annotated[
            str,
            Field(description="Payment terms for invoicing: due_on_receipt | net_30 | net_60 | net_90."),
        ] = "net_30",
    ) -> dict[str, Any]:
        # NOTE: Keep inputs flat and deterministic. We reuse existing BL entrypoints; no business logic here.
        trace = Trace(
            tool="workflow_order_to_cash",
            input_redacted={
                "session_id": "<redacted>",
                "customer": customer,
                "items": items,
                "notes": notes,
                "auto_approve": auto_approve,
                "payment_terms": payment_terms,
            },
        )

        # Import locally to avoid circular imports between tool modules.
        from softone_mcp.business.orders import create_order_bl  # pylint: disable=import-outside-toplevel
        from softone_mcp.business.exceptions import (  # pylint: disable=import-outside-toplevel
            CustomerNotFoundError,
            InsufficientStockError,
            ItemNotFoundError,
        )
        from softone_mcp.internal.adapters.repositories import (  # pylint: disable=import-outside-toplevel
            SoftOneCustomerRepository,
            SoftOneItemRepository,
            SoftOneOrderItemsRepository,
            SoftOneOrderRepository,
        )

        cust_q = (customer or "").strip()
        if not cust_q:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid request. customer is required.",
                    {"customer": customer},
                ),
                meta=trace.meta(),
            )

        customers_repo = SoftOneCustomerRepository(client, session_id)
        items_repo = SoftOneItemRepository(client, session_id)
        orders_repo = SoftOneOrderRepository(client, session_id)
        orderitems_repo = SoftOneOrderItemsRepository(client, session_id)
        inventory = SoftOneInventoryService(client, session_id)
        invoices_repo = SoftOneInvoiceRepository(client, session_id)

        # 1) Resolve customer id
        with trace.action("resolve_customer_id", detail={"q": cust_q}) as ctx:
            try:
                customer_id = int(cust_q)
                ctx["resolution"] = "int"
            except ValueError:
                ctx["resolution"] = "lookup"
                found = customers_repo.resolve_id(q=cust_q)
                if found is None:
                    return err(
                        SoftOneError(
                            SOFTONE_NOT_FOUND_CODE,
                            "Invalid request, Data does not exist.",
                            {"customer": cust_q},
                        ),
                        meta=trace.meta(),
                    )
                customer_id = found
            ctx["customer_id"] = customer_id

        # 2) Resolve item ids deterministically
        resolved_lines: list[dict[str, Any]] = []
        with trace.action("resolve_item_ids", detail={"lines": len(items)}):
            for ln in items:
                q = str((ln or {}).get("item_name_or_id") or "").strip()
                qty_raw = (ln or {}).get("quantity")
                if not q:
                    return err(
                        SoftOneError(
                            SOFTONE_BAD_INPUT_CODE,
                            "Invalid request. item_name_or_id is required for every line.",
                            {"line": ln},
                        ),
                        meta=trace.meta(),
                    )
                try:
                    qty = int(qty_raw)
                except (TypeError, ValueError):
                    return err(
                        SoftOneError(
                            SOFTONE_BAD_INPUT_CODE,
                            "Invalid request. quantity must be an integer.",
                            {"line": ln},
                        ),
                        meta=trace.meta(),
                    )
                if qty <= 0:
                    return err(
                        SoftOneError(
                            SOFTONE_BAD_INPUT_CODE,
                            "Invalid request. quantity must be > 0.",
                            {"line": ln},
                        ),
                        meta=trace.meta(),
                    )

                try:
                    item_id = int(q)
                except ValueError:
                    found = items_repo.resolve_id(q=q)
                    if found is None:
                        return err(
                            SoftOneError(
                                SOFTONE_NOT_FOUND_CODE,
                                "Invalid request, Data does not exist.",
                                {"item_name_or_id": q},
                            ),
                            meta=trace.meta(),
                        )
                    item_id = found
                resolved_lines.append({"item_id": int(item_id), "quantity": int(qty)})

        # 3) Create order (reservations happen here)
        with trace.action("create_order", detail={"customer_id": customer_id, "lines": len(resolved_lines)}):
            try:
                order = create_order_bl(
                    customers_repo,
                    items_repo,
                    orders_repo,
                    orderitems_repo,
                    inventory,
                    customer_id=int(customer_id),
                    items=resolved_lines,
                    notes=notes,
                    auto_approve_policy=auto_approve,
                )
            except CustomerNotFoundError as e:
                return err(
                    SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"customer_id": e.customer_id}),
                    meta=trace.meta(),
                )
            except ItemNotFoundError as e:
                return err(
                    SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"item_id": e.item_id}),
                    meta=trace.meta(),
                )
            except InsufficientStockError as e:
                return err(
                    SoftOneError(
                        SOFTONE_BAD_INPUT_CODE,
                        str(e),
                        {"item_id": e.item_id, "requested": e.requested, "available": e.available},
                    ),
                    meta=trace.meta(),
                )
            except ValueError as e:
                return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(e), {}), meta=trace.meta())
            except SoftOneError as e:
                return err(e, meta=trace.meta())

        order_id = int(order.get("order_id") or order.get("id") or 0)
        status = str(order.get("status") or "")
        if not order_id:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Workflow failed: create_order did not return an order id.",
                    {"order": order},
                ),
                meta=trace.meta(),
            )

        # 4) Invoice only if Confirmed (per your choice: never auto-approve here)
        with trace.action("create_invoice_if_confirmed", detail={"order_id": order_id, "status": status}):
            if status != "Confirmed":
                return err(
                    SoftOneError(
                        SOFTONE_BAD_INPUT_CODE,
                        "Order is not Confirmed; cannot invoice in this workflow.",
                        {
                            "order_id": order_id,
                            "current_status": status,
                            "expected_status": "Confirmed",
                            "hint": (
                                "Either use auto_approve='always' on the order step "
                                "or call approve_order before invoicing."
                            ),
                        },
                    ),
                    meta=trace.meta(),
                )

            try:
                invoice = create_invoice_bl(
                    orders_repo,
                    invoices_repo,
                    inventory,
                    order_id=order_id,
                    payment_terms=payment_terms,
                )
            except OrderNotFoundError as e:
                return err(SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}), meta=trace.meta())
            except InvalidOrderStatusError as e:
                return err(
                    SoftOneError(
                        SOFTONE_BAD_INPUT_CODE,
                        str(e),
                        {"order_id": e.order_id, "current_status": e.current, "expected_status": e.expected},
                    ),
                    meta=trace.meta(),
                )
            except InvalidPaymentTermsError as e:
                return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(e), {"terms": e.terms}), meta=trace.meta())
            except SoftOneError as e:
                return err(e, meta=trace.meta())

        return ok({"order": order, "invoice": invoice}, meta=trace.meta())

    @mcp.tool(name="get_unpaid_invoices", description=(
        "Fetch all unpaid invoices. "
        "Optionally filter by customer_id for a per-customer collections view."
    ))
    def get_unpaid_invoices_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        customer_id: Annotated[
            str,
            Field(description="Filter by customer ID. Leave empty to get all unpaid invoices."),
        ] = "",
    ) -> dict[str, Any]:
        # Parse customer_id — empty means "no filter".
        cust: int | None
        if customer_id.strip():
            try:
                cust = int(customer_id)
            except ValueError:
                return err(SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid customer_id. Expected an integer.",
                    {"customer_id": customer_id},
                ))
        else:
            cust = None

        invoices_repo = SoftOneInvoiceRepository(client, session_id)
        try:
            data = get_unpaid_invoices_bl(invoices_repo, customer_id=cust)
            return ok(data)
        except SoftOneError as e:
            return err(e)

    @mcp.tool(name="get_invoice", description="Fetch a single invoice by ID.")
    def get_invoice_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        invoice_id: Annotated[
            int, Field(description="ID of the invoice to fetch")
        ],
    ) -> dict[str, Any]:
        invoices_repo = SoftOneInvoiceRepository(client, session_id)
        try:
            data = get_invoice_bl(invoices_repo, invoice_id=invoice_id)
            return ok(data)
        except InvoiceNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"invoice_id": e.invoice_id}
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="list_invoices",
        description=(
            "List invoices (mock-only). Optional filters: status, customer_id. "
            "Use this for visibility and collections workflows."
        ),
    )
    def list_invoices_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        status: Annotated[
            str,
            Field(description="Filter by status (unpaid|partial|paid). Leave empty for all."),
        ] = "",
        customer_id: Annotated[
            str,
            Field(description="Filter by customer ID. Leave empty for all customers."),
        ] = "",
    ) -> dict[str, Any]:
        cust: int | None = None
        if customer_id.strip():
            try:
                cust = int(customer_id)
            except ValueError:
                return err(SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid customer_id. Expected an integer.",
                    {"customer_id": customer_id},
                ))

        invoices_repo = SoftOneInvoiceRepository(client, session_id)
        try:
            data = list_invoices_bl(invoices_repo, status=status, customer_id=cust)
            return ok(data)
        except SoftOneError as e:
            return err(e)
