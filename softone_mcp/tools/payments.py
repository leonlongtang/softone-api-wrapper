"""
Agent-facing payment tools.

Layer contract:
    - This layer OWNS the `{ok, data}` / `{ok, error}` envelope.
    - Wrap every successful business-layer result with ok(...).
    - Catch SoftOneError and domain exceptions, and return err(...).

Tool inputs are intentionally FLAT (no nested `inp: SomeModel` wrapper):
LLMs generate tool-calls far more reliably against flat JSON schemas than
against nested ones. Validation/descriptions are preserved via
`Annotated[type, Field(...)]`.

Note on `amount`: exposed as a string so the Inspector / less-structured
LLM clients can type freely; we parse it to float inside the tool and
return a clean error envelope on bad input.
"""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from softone_mcp.business.constants import SOFTONE_BAD_INPUT_CODE, SOFTONE_NOT_FOUND_CODE
from softone_mcp.business.exceptions import (
    InvoiceAlreadyPaidError,
    InvoiceNotFoundError,
    PaymentExceedsBalanceError,
    PaymentNotFoundError,
)
from softone_mcp.business.payments import (
    delete_payment_bl,
    get_payment_bl,
    list_payments_for_invoice_bl,
    record_payment_bl,
)
from softone_mcp.deps import err, ok
from softone_mcp.internal.adapters.repositories import (
    SoftOneInvoiceRepository,
    SoftOnePaymentRepository,
)
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError

# ---------------------------------------------------------------------------
# MCP tool registrations
# ---------------------------------------------------------------------------

def register_payment_tools(mcp: FastMCP, client: SoftOneClient) -> None:

    @mcp.tool(name="record_payment", description=(
        "Record a payment against an invoice. "
        "In the mock backend, the invoice status is automatically refreshed "
        "(unpaid → partial → paid) based on the sum of payments."
    ))
    def record_payment_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        invoice_id: Annotated[
            int, Field(description="ID of the invoice being paid.")
        ],
        amount: Annotated[
            str,
            Field(description="Payment amount (e.g. '100.00'). Parsed as a float."),
        ],
        payment_date: Annotated[
            str,
            Field(description="Optional ISO date (YYYY-MM-DD). Leave empty to default to now."),
        ] = "",
    ) -> dict[str, Any]:
        # Parse amount first so we can return a clean error for non-numeric input.
        try:
            parsed_amount = float(amount)
        except ValueError:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid amount. Expected a number.",
                {"amount": amount},
            ))

        invoices_repo = SoftOneInvoiceRepository(client, session_id)
        payments_repo = SoftOnePaymentRepository(client, session_id)
        try:
            data = record_payment_bl(
                invoices_repo,
                payments_repo,
                invoice_id=invoice_id,
                amount=parsed_amount,
                payment_date=payment_date,
            )
            return ok(data)
        except ValueError as ve:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(ve),
                {"amount": parsed_amount, "invoice_id": invoice_id},
            ))
        except InvoiceNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"invoice_id": e.invoice_id},
            ))
        except InvoiceAlreadyPaidError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(e),
                {
                    "invoice_id": e.invoice_id,
                    "hint": (
                        "Use refund_payment to reverse an existing payment "
                        "before recording a new one."
                    ),
                },
            ))
        except PaymentExceedsBalanceError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(e),
                {
                    "invoice_id": e.invoice_id,
                    "amount": e.amount,
                    "outstanding": e.outstanding,
                },
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="list_invoice_payments",
        description=(
            "List all payments recorded against an invoice. "
            "Returns id, invoice_id, amount, and payment_date for each row."
        ),
    )
    def list_invoice_payments_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        invoice_id: Annotated[
            int, Field(description="ID of the invoice whose payments to list.")
        ],
    ) -> dict[str, Any]:
        invoices_repo = SoftOneInvoiceRepository(client, session_id)
        payments_repo = SoftOnePaymentRepository(client, session_id)
        try:
            data = list_payments_for_invoice_bl(
                invoices_repo,
                payments_repo,
                invoice_id=invoice_id,
            )
            return ok(data)
        except InvoiceNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"invoice_id": e.invoice_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(name="get_payment", description="Fetch a single payment by ID.")
    def get_payment_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        payment_id: Annotated[
            int, Field(description="ID of the payment to fetch.")
        ],
    ) -> dict[str, Any]:
        payments_repo = SoftOnePaymentRepository(client, session_id)
        try:
            data = get_payment_bl(
                payments_repo,
                key=payment_id,
            )
            return ok(data)
        except PaymentNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"payment_id": e.payment_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(name="refund_payment", description=(
        "Refund (delete) a payment by ID. "
        "In the mock backend, the associated invoice status is rolled back "
        "(paid → partial → unpaid) as the sum of payments drops."
    ))
    def refund_payment_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        payment_id: Annotated[
            int, Field(description="ID of the payment to refund (delete).")
        ],
    ) -> dict[str, Any]:
        payments_repo = SoftOnePaymentRepository(client, session_id)
        try:
            data = delete_payment_bl(
                payments_repo,
                key=payment_id,
            )
            return ok(data)
        except PaymentNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"payment_id": e.payment_id},
            ))
        except SoftOneError as e:
            return err(e)
