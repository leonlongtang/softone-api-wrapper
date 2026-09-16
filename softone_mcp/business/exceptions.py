# softone_mcp/business/exceptions.py


class CustomerNotFoundError(Exception):
    def __init__(self, customer_id: int):
        super().__init__(f"Customer {customer_id} not found")
        self.customer_id = customer_id


class ItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        super().__init__(f"Item {item_id} not found")
        self.item_id = item_id


class InsufficientStockError(Exception):
    def __init__(self, item_id: int, requested: int, available: int):
        super().__init__(
            f"Item {item_id}: requested {requested}, only {available} available"
        )
        self.item_id = item_id
        self.requested = requested
        self.available = available


class OrderNotFoundError(Exception):
    def __init__(self, order_id: int):
        super().__init__(f"Order {order_id} not found")
        self.order_id = order_id


class InvalidOrderStatusError(Exception):
    def __init__(self, order_id: int, current: str, expected: str):
        super().__init__(
            f"Order {order_id} is '{current}', expected '{expected}'"
        )
        self.order_id = order_id
        self.current = current
        self.expected = expected


class InvoiceNotFoundError(Exception):
    def __init__(self, invoice_id: int):
        super().__init__(f"Invoice {invoice_id} not found")
        self.invoice_id = invoice_id


class InvalidPaymentTermsError(Exception):
    def __init__(self, terms: str):
        super().__init__(
            f"Unknown payment terms '{terms}'. "
            f"Use: 'net_30', 'net_60', 'net_90', 'due_on_receipt'"
        )
        self.terms = terms


class PaymentNotFoundError(Exception):
    def __init__(self, payment_id: int):
        super().__init__(f"Payment {payment_id} not found")
        self.payment_id = payment_id


class InvoiceAlreadyPaidError(Exception):
    """
    Raised when a caller tries to record a payment against an invoice whose
    outstanding balance is zero. The strict policy is: once paid, no more
    payments — use `refund_payment` first if you need to correct a mistake.
    """

    def __init__(self, invoice_id: int):
        super().__init__(f"Invoice {invoice_id} is already fully paid")
        self.invoice_id = invoice_id


class PaymentExceedsBalanceError(Exception):
    """
    Raised when a single payment would push `sum(payments) > invoice.amount`.
    The error payload carries the outstanding balance so the agent can retry
    with a corrected amount without an extra round-trip.
    """

    def __init__(self, invoice_id: int, amount: float, outstanding: float):
        super().__init__(
            f"Payment of {amount:.2f} exceeds outstanding balance "
            f"({outstanding:.2f}) on invoice {invoice_id}"
        )
        self.invoice_id = invoice_id
        self.amount = amount
        self.outstanding = outstanding