"""login / authenticate flows.

Covers:
  - login() with full selection -> final clientID directly
  - login() with no selection -> temporary clientID + objs list
  - login() bad credentials -> WsError(-2)
  - authenticate() promotes a temporary clientID to a final one
  - authenticate() with bad selection -> WsError(-2)
  - authenticate() with unknown clientID -> WsError(-1)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mock_db.mock_ws import WsError, authenticate, login

SEED_CREDS = {"username": "john", "password": "aitis", "appId": "2001"}
SEED_SELECTION = {"COMPANY": "1000", "BRANCH": "1000", "MODULE": "0", "REFID": "1"}


class TestLogin:
    def test_login_with_selection_returns_final_client_id(self, db_path: Path) -> None:
        resp = login(db_path=db_path, **SEED_CREDS, **SEED_SELECTION)

        assert resp["success"] is True
        assert isinstance(resp["clientID"], str) and resp["clientID"]
        # Final-tier login goes straight to a session; no `objs` payload.
        assert "objs" not in resp

    def test_login_without_selection_returns_temp_client_id_and_objs(
        self, db_path: Path
    ) -> None:
        resp = login(db_path=db_path, **SEED_CREDS)

        assert resp["success"] is True
        assert isinstance(resp["clientID"], str) and resp["clientID"]
        # Temp-tier login MUST include the available selections.
        assert "objs" in resp and isinstance(resp["objs"], list)
        assert len(resp["objs"]) >= 1
        first = resp["objs"][0]
        assert {"COMPANY", "COMPANYNAME", "BRANCH", "MODULE", "REFID"} <= first.keys()

    @pytest.mark.parametrize(
        "bad_creds",
        [
            {"username": "john", "password": "WRONG", "appId": "2001"},
            {"username": "ghost", "password": "aitis", "appId": "2001"},
            {"username": "john", "password": "aitis", "appId": "9999"},
        ],
        ids=["bad_password", "unknown_user", "wrong_app_id"],
    )
    def test_login_rejects_bad_credentials(
        self, db_path: Path, bad_creds: dict
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            login(db_path=db_path, **bad_creds)
        assert exc_info.value.code == -2


class TestAuthenticate:
    def test_authenticate_promotes_temp_to_final(self, db_path: Path) -> None:
        login_resp = login(db_path=db_path, **SEED_CREDS)
        temp_id = login_resp["clientID"]

        auth_resp = authenticate(
            clientID=temp_id, db_path=db_path, **SEED_SELECTION
        )

        assert auth_resp["success"] is True
        # The promoted clientID is a NEW token; the temp one shouldn't
        # silently keep working as final.
        final_id = auth_resp["clientID"]
        assert isinstance(final_id, str) and final_id
        assert final_id != temp_id

    def test_authenticate_idempotent_for_already_final_session(
        self, db_path: Path
    ) -> None:
        # Drive a final-tier login then re-authenticate -- should be a no-op.
        final_id = login(db_path=db_path, **SEED_CREDS, **SEED_SELECTION)["clientID"]

        resp = authenticate(clientID=final_id, db_path=db_path, **SEED_SELECTION)

        assert resp["success"] is True
        assert resp["clientID"] == final_id

    def test_authenticate_unknown_client_id(self, db_path: Path) -> None:
        with pytest.raises(WsError) as exc_info:
            authenticate(clientID="not-a-real-token", db_path=db_path, **SEED_SELECTION)
        assert exc_info.value.code == -1

    def test_authenticate_with_wrong_selection_fails(self, db_path: Path) -> None:
        temp_id = login(db_path=db_path, **SEED_CREDS)["clientID"]

        with pytest.raises(WsError) as exc_info:
            authenticate(
                clientID=temp_id,
                db_path=db_path,
                COMPANY="9999",  # not seeded
                BRANCH="1000",
                MODULE="0",
                REFID="1",
            )
        assert exc_info.value.code == -2
