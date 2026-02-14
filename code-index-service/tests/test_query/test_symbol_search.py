# -*- coding: utf-8 -*-
"""Tests for symbol search query module."""

import os
import pytest

from src.config import SQLITE_DB_PATH
from src.storage.schema import init_db
from src.storage.sqlite_store import SqliteStore
from src.query.symbol_search import search_symbols


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Set up a test DB with sample data."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    # Patch the config module
    import src.config
    monkeypatch.setattr(src.config, "SQLITE_DB_PATH", tmp_path / "test.db")

    # Also patch the import in query module
    import src.query.symbol_search as ss
    original_get = ss.get_connection
    ss.get_connection = lambda path: __import__("src.storage.schema", fromlist=["get_connection"]).get_connection(db_path)

    store = SqliteStore(db_path)
    cid = store.create_codebase("/workspace", "java")
    fid = store.upsert_file(cid, "Test.java", "h1", "java", 100)

    store.insert_symbols_batch([
        {"file_id": fid, "fqn": "com.bank.loan.controller.LoanController", "name": "LoanController",
         "symbol_type": "CLASS", "line_start": 10, "line_end": 50, "signature": "public class LoanController",
         "parent_fqn": "", "visibility": "public"},
        {"file_id": fid, "fqn": "com.bank.loan.controller.LoanController.apply", "name": "apply",
         "symbol_type": "METHOD", "line_start": 20, "line_end": 30, "signature": "public Response apply(LoanRequest req)",
         "parent_fqn": "com.bank.loan.controller.LoanController", "visibility": "public"},
        {"file_id": fid, "fqn": "com.bank.loan.service.LoanService", "name": "LoanService",
         "symbol_type": "CLASS", "line_start": 1, "line_end": 80, "signature": "public class LoanService",
         "parent_fqn": "", "visibility": "public"},
    ])

    yield db_path

    ss.get_connection = original_get


class TestSymbolSearch:
    def test_exact_match(self, setup_db):
        results = search_symbols("LoanController")
        assert len(results) >= 1
        assert any(r["name"] == "LoanController" for r in results)

    def test_wildcard_pattern(self, setup_db):
        results = search_symbols("*Loan*")
        assert len(results) >= 2  # LoanController + LoanService + method

    def test_type_filter(self, setup_db):
        results = search_symbols("*Loan*", symbol_type="CLASS")
        assert all(r["type"] == "CLASS" for r in results)

    def test_limit(self, setup_db):
        results = search_symbols("*", limit=1)
        assert len(results) == 1

    def test_no_results(self, setup_db):
        results = search_symbols("NonExistentClass12345")
        assert len(results) == 0
