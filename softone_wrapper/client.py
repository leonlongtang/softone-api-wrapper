from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .domain.errors import SoftOneError
from .domain.models import LoginSelection, SoftOneSession
from .infrastructure.gateway import SoftOneGateway
from .infrastructure.http_gateway import HttpGateway, HttpGatewayConfig
from .infrastructure.mock_gateway import MockGateway
from .infrastructure.session_store import InMemorySessionStore
from .serialization.responses import raise_for_softone_error


@dataclass(frozen=True)
class StartConnectionResult:
    """
    Result of `start_connection`.

    If `session` is present, the connection is ready.
    If `selections` is present, you must choose one and call `complete_connection`.
    """

    session: Optional[SoftOneSession]
    temp_client_id: Optional[str]
    selections: Optional[list[LoginSelection]]


class SoftOneClient:
    def __init__(
        self,
        *,
        gateway: Optional[SoftOneGateway] = None,
        session_store: Optional[InMemorySessionStore] = None,
        default_session_hours: int = 8,
    ) -> None:
        self._gateway = gateway or HttpGateway(config=HttpGatewayConfig())
        self._sessions = session_store or InMemorySessionStore()
        self._default_session_hours = default_session_hours

    @classmethod
    def mock(cls, db_path: Path | None = None) -> "SoftOneClient":
        """
        Build a client backed by the local SQLite mock.

        When `db_path` is set (e.g. in tests), the mock WS uses that file
        instead of the packaged default seed DB.
        """
        gw = MockGateway(db_path=db_path) if db_path is not None else MockGateway()
        return cls(gateway=gw)

    def _call(self, *, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._gateway.call(base_url=base_url, payload=payload)
        raise_for_softone_error(resp)
        return resp

    # ---------------------------------------------------------------------
    # Mock-only query helpers (kept on the client so upper layers stay pure)
    # ---------------------------------------------------------------------

    def get_session_context(self, *, session_id: str) -> dict[str, Any]:
        """
        Return the stored session selection context.

        This is safe to expose to tools/agents and is useful for debugging and
        for making agent flows context-aware (company/branch/module/refid).
        """
        s = self._sessions.get(session_id)
        return {
            "session_id": s.session_id,
            "company": s.company,
            "branch": s.branch,
            "module": s.module,
            "refid": s.refid,
        }

    def resolve_customer_id(self, *, session_id: str, q: str) -> int | None:
        """
        Mock-only: resolve a customer name/code to a numeric id.

        In real mode this raises SoftOneError(-9, ...) to avoid silently
        depending on mock-only capabilities.
        """
        _ = self._sessions.get(session_id)  # validate session_id exists/active
        if hasattr(self._gateway, "resolve_customer_id"):
            return getattr(self._gateway, "resolve_customer_id")(q)
        raise SoftOneError(-9, "Customer lookup by name/code is only supported in mock mode.", {"q": q})

    def resolve_item_id(self, *, session_id: str, q: str) -> int | None:
        _ = self._sessions.get(session_id)
        if hasattr(self._gateway, "resolve_item_id"):
            return getattr(self._gateway, "resolve_item_id")(q)
        raise SoftOneError(-9, "Item lookup by name/code is only supported in mock mode.", {"q": q})

    def search_customers(
        self,
        *,
        session_id: str,
        q: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = self._sessions.get(session_id)
        if hasattr(self._gateway, "search_customers"):
            return getattr(self._gateway, "search_customers")(q=q, limit=limit)
        raise SoftOneError(
            -9,
            "Searching customers is only supported in mock mode.",
            {"q": q, "limit": limit},
        )

    def search_items(
        self,
        *,
        session_id: str,
        q: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = self._sessions.get(session_id)
        if hasattr(self._gateway, "search_items"):
            return getattr(self._gateway, "search_items")(q=q, limit=limit)
        raise SoftOneError(
            -9,
            "Searching items is only supported in mock mode.",
            {"q": q, "limit": limit},
        )

    def list_invoices(
        self,
        *,
        session_id: str,
        status: str = "",
        customer_id: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = self._sessions.get(session_id)
        if hasattr(self._gateway, "list_invoices"):
            return getattr(self._gateway, "list_invoices")(status=status, customer_id=customer_id)
        raise SoftOneError(-9, "Listing invoices is only supported in mock mode.", {"status": status, "customer_id": customer_id})

    def list_orders(
        self,
        *,
        session_id: str,
        status: str = "",
        customer_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = self._sessions.get(session_id)
        if hasattr(self._gateway, "list_orders"):
            return getattr(self._gateway, "list_orders")(
                status=status, customer_id=customer_id, limit=limit
            )
        raise SoftOneError(
            -9,
            "Listing orders is only supported in mock mode.",
            {"status": status, "customer_id": customer_id, "limit": limit},
        )

    def list_payments_for_invoice(
        self,
        *,
        session_id: str,
        invoice_id: int,
    ) -> list[dict[str, Any]]:
        _ = self._sessions.get(session_id)
        if hasattr(self._gateway, "list_payments_for_invoice"):
            return getattr(self._gateway, "list_payments_for_invoice")(invoice_id)
        raise SoftOneError(-9, "Listing payments by invoice is only supported in mock mode.", {"invoice_id": invoice_id})

    def start_connection(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        app_id: str,
        # Optional: if caller already knows the selection, we can skip authenticate
        company: Optional[str] = None,
        branch: Optional[str] = None,
        module: Optional[str] = None,
        refid: Optional[str] = None,
        session_hours: Optional[int] = None,
    ) -> StartConnectionResult:
        """
        Implements the flow documented in docs/softone_ws_reference.md:
        - call `login`
        - if selection provided: returns final clientID directly (ready session)
        - else: returns selections + temporary clientID (needs `complete_connection`)
        """
        payload: dict[str, Any] = {
            "service": "login",
            "username": username,
            "password": password,
            "appId": app_id,
        }

        selection_provided = all(v is not None for v in (company, branch, module, refid))
        if selection_provided:
            payload.update(
                {"COMPANY": company, "BRANCH": branch, "MODULE": module, "REFID": refid}
            )

        resp = self._call(base_url=base_url, payload=payload)

        expires_at: Optional[datetime] = None
        sh = session_hours if session_hours is not None else self._default_session_hours
        if sh is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=sh)

        if selection_provided:
            session_id = self._sessions.new_session_id()
            self._sessions.put(
                session_id=session_id,
                base_url=base_url,
                app_id=app_id,
                client_id=str(resp["clientID"]),
                expires_at=expires_at,
                company=company,
                branch=branch,
                module=module,
                refid=refid,
            )
            return StartConnectionResult(
                session=self._sessions.get(session_id),
                temp_client_id=None,
                selections=None,
            )

        objs = resp.get("objs") or []
        selections = [
            LoginSelection(
                COMPANY=o["COMPANY"],
                COMPANYNAME=o.get("COMPANYNAME", ""),
                BRANCH=o["BRANCH"],
                BRANCHNAME=o.get("BRANCHNAME", ""),
                MODULE=o["MODULE"],
                MODULENAME=o.get("MODULENAME", ""),
                REFID=o["REFID"],
                REFIDNAME=o.get("REFIDNAME", ""),
            )
            for o in objs
        ]

        return StartConnectionResult(
            session=None,
            temp_client_id=str(resp["clientID"]),
            selections=selections,
        )

    def complete_connection(
        self,
        *,
        base_url: str,
        app_id: str,
        temp_client_id: str,
        selection: LoginSelection,
        session_hours: Optional[int] = None,
    ) -> SoftOneSession:
        payload = {
            "service": "authenticate",
            "clientID": temp_client_id,
            "COMPANY": selection.COMPANY,
            "BRANCH": selection.BRANCH,
            "MODULE": selection.MODULE,
            "REFID": selection.REFID,
        }
        resp = self._call(base_url=base_url, payload=payload)

        expires_at: Optional[datetime] = None
        sh = session_hours if session_hours is not None else self._default_session_hours
        if sh is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=sh)

        session_id = self._sessions.new_session_id()
        self._sessions.put(
            session_id=session_id,
            base_url=base_url,
            app_id=app_id,
            client_id=str(resp["clientID"]),
            expires_at=expires_at,
            company=selection.COMPANY,
            branch=selection.BRANCH,
            module=selection.MODULE,
            refid=selection.REFID,
        )
        return self._sessions.get(session_id)

    def getObjects(self, *, session_id: str) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        return self._call(base_url=s.base_url, payload={"service": "getObjects", "clientID": s.client_id, "appId": s.app_id})

    def getObjectTables(self, *, session_id: str, OBJECT: str) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        return self._call(
            base_url=s.base_url,
            payload={"service": "getObjectTables", "clientID": s.client_id, "appId": s.app_id, "OBJECT": OBJECT},
        )

    def getTableFields(self, *, session_id: str, OBJECT: str, TABLE: str) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        return self._call(
            base_url=s.base_url,
            payload={
                "service": "getTableFields",
                "clientID": s.client_id,
                "appId": s.app_id,
                "OBJECT": OBJECT,
                "TABLE": TABLE,
            },
        )

    def getBrowserInfo(
        self,
        *,
        session_id: str,
        OBJECT: str,
        LIST: str = "",
        FILTERS: str = "",
        VERSION: Optional[int] = None,
        LIMIT: Optional[int] = None,
    ) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        payload: dict[str, Any] = {
            "service": "getBrowserInfo",
            "clientID": s.client_id,
            "appId": s.app_id,
            "OBJECT": OBJECT,
            "LIST": LIST,
        }
        if FILTERS:
            payload["FILTERS"] = FILTERS
        if VERSION is not None:
            payload["VERSION"] = VERSION
        if LIMIT is not None:
            payload["LIMIT"] = LIMIT
        return self._call(base_url=s.base_url, payload=payload)

    def selectorFields(
        self,
        *,
        session_id: str,
        TABLENAME: str,
        KEYNAME: str,
        KEYVALUE: Any,
        RESULTFIELDS: str,
    ) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        return self._call(
            base_url=s.base_url,
            payload={
                "service": "selectorFields",
                "clientID": s.client_id,
                "appId": s.app_id,
                "TABLENAME": TABLENAME,
                "KEYNAME": KEYNAME,
                "KEYVALUE": KEYVALUE,
                "RESULTFIELDS": RESULTFIELDS,
            },
        )

    def SqlData(self, *, session_id: str, SqlName: str, **params: Any) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        payload: dict[str, Any] = {
            "service": "SqlData",
            "clientID": s.client_id,
            "appId": s.app_id,
            "SqlName": SqlName,
        }
        payload.update(params)
        return self._call(base_url=s.base_url, payload=payload)

    def eInvoice(self, *, session_id: str, key: str, template: str) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        return self._call(
            base_url=s.base_url,
            payload={
                "service": "eInvoice",
                "clientID": s.client_id,
                "appId": s.app_id,
                "key": key,
                "template": template,
            },
        )

    def getData(
        self,
        *,
        session_id: str,
        OBJECT: str,
        KEY: Any,
        FORM: str = "",
        LOCATEINFO: str = "",
    ) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        payload: dict[str, Any] = {
            "service": "getData",
            "clientID": s.client_id,
            "appId": s.app_id,
            "OBJECT": OBJECT,
            "FORM": FORM,
            "KEY": KEY,
        }
        if LOCATEINFO:
            payload["LOCATEINFO"] = LOCATEINFO
        return self._call(base_url=s.base_url, payload=payload)

    def setData(
        self,
        *,
        session_id: str,
        OBJECT: str,
        data: dict[str, Any],
        KEY: Optional[str] = None,
        VERSION: Optional[int] = None,
        LOCATEINFO: str = "",
    ) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        payload: dict[str, Any] = {
            "service": "setData",
            "clientID": s.client_id,
            "appId": s.app_id,
            "OBJECT": OBJECT,
            "data": data,
        }
        if KEY is not None:
            payload["KEY"] = KEY
        if VERSION is not None:
            payload["VERSION"] = VERSION
        if LOCATEINFO:
            payload["LOCATEINFO"] = LOCATEINFO
        return self._call(base_url=s.base_url, payload=payload)

    def calculate(
        self,
        *,
        session_id: str,
        OBJECT: str,
        KEY: Any,
        data: dict[str, Any],
        LOCATEINFO: str = "",
    ) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        payload: dict[str, Any] = {
            "service": "calculate",
            "clientID": s.client_id,
            "appId": s.app_id,
            "OBJECT": OBJECT,
            "KEY": KEY,
            "data": data,
        }
        if LOCATEINFO:
            payload["LOCATEINFO"] = LOCATEINFO
        return self._call(base_url=s.base_url, payload=payload)

    def delData(self, *, session_id: str, OBJECT: str, KEY: Any, FORM: str = "") -> dict[str, Any]:
        s = self._sessions.get(session_id)
        return self._call(
            base_url=s.base_url,
            payload={
                "service": "delData",
                "clientID": s.client_id,
                "appId": s.app_id,
                "OBJECT": OBJECT,
                "FORM": FORM,
                "KEY": KEY,
            },
        )

