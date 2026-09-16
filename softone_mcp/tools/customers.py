"""
Agent-facing customer tools.

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

from .utils import slug, deterministic_suffix

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from softone_mcp.business.constants import SOFTONE_BAD_INPUT_CODE, SOFTONE_NOT_FOUND_CODE
from softone_mcp.business.customers import (
    create_customer_bl,
    delete_customer_bl,
    get_customer_bl,
    update_customer_bl,
)
from softone_mcp.business.exceptions import CustomerNotFoundError
from softone_mcp.deps import err, ok
from softone_mcp.internal.adapters.repositories import SoftOneCustomerRepository
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError


def register_customer_tools(mcp: FastMCP, client: SoftOneClient) -> None:

    @mcp.tool(name="create_customer", description="Business action: create a customer.")
    def create_customer_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name: Annotated[str, Field(description="Customer name.")],
        code: Annotated[
            str,
            Field(description="Customer code. Leave empty to auto-generate."),
        ] = "",
        afm: Annotated[
            str, Field(description="Tax id (AFM). Leave empty to omit.")
        ] = "",
        email: Annotated[
            str, Field(description="Email. Leave empty to omit.")
        ] = "",
        phone: Annotated[
            str, Field(description="Phone. Leave empty to omit.")
        ] = "",
        address: Annotated[
            str, Field(description="Address. Leave empty to omit.")
        ] = "",
        balance: Annotated[
            str, Field(description="Opening balance. Leave empty to omit.")
        ] = "",
        created_at: Annotated[
            str, Field(description="Optional created_at ISO string. Leave empty to omit.")
        ] = "",
    ) -> dict[str, Any]:
        final_code = code.strip() or f"AG-{slug(name)[:16]}-{deterministic_suffix(name)}"
        customers_repo = SoftOneCustomerRepository(client, session_id)
        try:
            data = create_customer_bl(
                customers_repo,
                code=final_code,
                name=name,
                afm=afm,
                email=email,
                phone=phone,  # matches CUSTOMER_OPTIONAL_KEYS in the internal layer
                address=address,
                balance=balance,
                created_at=created_at,
            )
            return ok(data)
        except ValueError as ve:
            return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(ve), {"name": name}))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="get_customer",
        description="Business action: get a customer by id or name/code (mock supports name/code lookup).",
    )
    def get_customer_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Customer id or name/code (mock supports name/code lookup)."),
        ],
        locateinfo: Annotated[
            str,
            Field(description="Optional locateinfo projection string (advanced)."),
        ] = "",
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        customers_repo = SoftOneCustomerRepository(client, session_id)

        # 1. Resolve `name_or_id` to a numeric id.
        try:
            key: int = int(q)
        except ValueError:
            try:
                found = customers_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        # 2. Delegate to the business layer and envelope the result.
        try:
            data = get_customer_bl(
                customers_repo,
                key=key,
                locateinfo=locateinfo,
            )
            return ok(data)
        except CustomerNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"customer_id": e.customer_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="update_customer",
        description=(
            "Patch a customer by id or name/code (mock resolves name/code). "
            "Omit fields (empty string) to leave them unchanged."
        ),
    )
    def update_customer_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Customer id or name/code (mock supports name/code lookup)."),
        ],
        code: Annotated[str, Field(description="New code. Leave empty to skip.")] = "",
        name: Annotated[str, Field(description="New name. Leave empty to skip.")] = "",
        email: Annotated[str, Field(description="New email. Leave empty to skip.")] = "",
        phone: Annotated[str, Field(description="New phone. Leave empty to skip.")] = "",
        afm: Annotated[str, Field(description="New tax id (AFM). Leave empty to skip.")] = "",
        address: Annotated[str, Field(description="New address. Leave empty to skip.")] = "",
        balance: Annotated[str, Field(description="New balance. Leave empty to skip.")] = "",
        created_at: Annotated[str, Field(description="New created_at. Leave empty to skip.")] = "",
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        customers_repo = SoftOneCustomerRepository(client, session_id)

        try:
            key: int = int(q)
        except ValueError:
            try:
                found = customers_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        patch: dict[str, Any] = {}
        if code.strip():
            patch["code"] = code.strip()
        if name.strip():
            patch["name"] = name.strip()
        if email.strip():
            patch["email"] = email.strip()
        if phone.strip():
            patch["phone"] = phone.strip()
        if afm.strip():
            patch["afm"] = afm.strip()
        if address.strip():
            patch["address"] = address.strip()
        if balance.strip():
            patch["balance"] = balance.strip()
        if created_at.strip():
            patch["created_at"] = created_at.strip()

        try:
            get_customer_bl(customers_repo, key=key, locateinfo="")
            data = update_customer_bl(customers_repo, key=key, **patch)
            return ok(data)
        except CustomerNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"customer_id": e.customer_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="delete_customer",
        description=(
            "Delete a customer by id or name/code (mock resolves name/code). "
            "Fails with referential integrity if the customer has orders or other dependents."
        ),
    )
    def delete_customer_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Customer id or name/code (mock supports name/code lookup)."),
        ],
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        customers_repo = SoftOneCustomerRepository(client, session_id)

        try:
            key: int = int(q)
        except ValueError:
            try:
                found = customers_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        try:
            get_customer_bl(customers_repo, key=key, locateinfo="")
            data = delete_customer_bl(customers_repo, key=key)
            return ok(data)
        except CustomerNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"customer_id": e.customer_id},
            ))
        except SoftOneError as e:
            return err(e)
