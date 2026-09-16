"""Shared pytest fixtures for the mock_db test suite.

Strategy:
    - `seeded_template_db` (session-scoped) builds the schema + seed once
      per test session. Slow part (~1.5s) happens exactly once.
    - `db_path` (function-scoped) copies the template to a fresh tempfile
      per test. Cheap (~5ms) and gives every test a pristine DB so tests
      can't bleed state into each other.
    - `final_session` returns a final-tier clientID by driving login()
      against `db_path`. Most authenticated services need this.

Tests that need to drive `handle_request` should:
    1. Take the `db_path` fixture (and `final_session` for sid).
    2. Pass `db_path=db_path` to handle_request.

Why this layout (and not session-shared DB):
    - The brain tests routinely mutate ORDER status, item stock, and create
      invoices. Sharing one DB makes test ordering matter. Function-scoped
      isolation is worth the few-ms-per-test overhead.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from mock_db.create_and_seed import create_schema, seed
from mock_db.mock_ws import login


@pytest.fixture(scope="session")
def seeded_template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the schema + seed once per session and cache the file path.

    Every per-test fixture below copies *this* file rather than re-seeding,
    which keeps the suite fast even with many tests.
    """
    template = tmp_path_factory.mktemp("mock_db_template") / "template.db"
    conn = sqlite3.connect(template)
    try:
        create_schema(conn)
        seed(conn)
        conn.commit()
    finally:
        conn.close()
    return template


@pytest.fixture
def db_path(seeded_template_db: Path, tmp_path: Path) -> Path:
    """A fresh, fully-seeded DB file per test."""
    fresh = tmp_path / "mock_softone.db"
    shutil.copyfile(seeded_template_db, fresh)
    return fresh


@pytest.fixture
def final_session(db_path: Path) -> str:
    """Drive login() to get a final-tier clientID for authenticated requests.

    Returns just the clientID string -- tests that also need the response
    can call `login(...)` directly with the same kwargs.
    """
    resp = login(
        username="john",
        password="aitis",
        appId="2001",
        COMPANY="1000",
        BRANCH="1000",
        MODULE="0",
        REFID="1",
        db_path=db_path,
    )
    return str(resp["clientID"])


@pytest.fixture
def raw_conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Direct sqlite connection for tests that bypass the WS layer.

    Used by `test_constraints.py` to verify schema-level rules (CHECK, FK,
    partial unique indexes) independently of the brain validators.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
