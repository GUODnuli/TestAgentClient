# -*- coding: utf-8 -*-
"""Tests for annotation search query module."""

import json
import pytest

from src.storage.schema import init_db
from src.storage.sqlite_store import SqliteStore
from src.query.annotation_search import search_by_annotation


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Set up a test DB with sample annotations."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    import src.query.annotation_search as ans
    ans.get_connection = lambda path: __import__("src.storage.schema", fromlist=["get_connection"]).get_connection(db_path)

    store = SqliteStore(db_path)
    cid = store.create_codebase("/workspace", "java")
    fid = store.upsert_file(cid, "Test.java", "h1", "java", 200)

    # Insert symbols
    store.insert_symbols_batch([
        {"file_id": fid, "fqn": "com.bank.controller.LoanController", "name": "LoanController",
         "symbol_type": "CLASS", "line_start": 10, "line_end": 100,
         "signature": "public class LoanController", "parent_fqn": "", "visibility": "public"},
        {"file_id": fid, "fqn": "com.bank.controller.LoanController.apply", "name": "apply",
         "symbol_type": "METHOD", "line_start": 25, "line_end": 40,
         "signature": "public Response apply(LoanRequest request)", "parent_fqn": "com.bank.controller.LoanController",
         "visibility": "public"},
        {"file_id": fid, "fqn": "com.bank.controller.LoanController.getStatus", "name": "getStatus",
         "symbol_type": "METHOD", "line_start": 45, "line_end": 55,
         "signature": "public Response getStatus(String id)", "parent_fqn": "com.bank.controller.LoanController",
         "visibility": "public"},
        {"file_id": fid, "fqn": "com.bank.service.LoanService", "name": "LoanService",
         "symbol_type": "CLASS", "line_start": 1, "line_end": 80,
         "signature": "public class LoanService", "parent_fqn": "", "visibility": "public"},
    ])

    # Insert annotations
    store.insert_annotations_batch([
        {"symbol_fqn": "com.bank.controller.LoanController", "annotation_name": "RestController",
         "scope": "CLASS", "params_json": "{}"},
        {"symbol_fqn": "com.bank.controller.LoanController", "annotation_name": "RequestMapping",
         "scope": "CLASS", "params_json": json.dumps({"value": "/api/loan"})},
        {"symbol_fqn": "com.bank.controller.LoanController.apply", "annotation_name": "TransCode",
         "scope": "METHOD", "params_json": json.dumps({"value": "LN_LOAN_APPLY", "name": "Loan Apply"})},
        {"symbol_fqn": "com.bank.controller.LoanController.apply", "annotation_name": "PostMapping",
         "scope": "METHOD", "params_json": json.dumps({"value": "/apply"})},
        {"symbol_fqn": "com.bank.controller.LoanController.getStatus", "annotation_name": "TransCode",
         "scope": "METHOD", "params_json": json.dumps({"value": "LN_STATUS_QUERY", "name": "Status Query"})},
        {"symbol_fqn": "com.bank.service.LoanService", "annotation_name": "Service",
         "scope": "CLASS", "params_json": "{}"},
    ])

    yield db_path

    ans.get_connection = lambda path: __import__("src.storage.schema", fromlist=["get_connection"]).get_connection(path)


class TestBasicSearch:
    def test_find_by_annotation_name(self, setup_db):
        results = search_by_annotation("TransCode", scope="METHOD")
        assert len(results) == 2

    def test_find_class_annotation(self, setup_db):
        results = search_by_annotation("RestController", scope="CLASS")
        assert len(results) == 1
        assert results[0]["fqn"] == "com.bank.controller.LoanController"

    def test_strip_at_prefix(self, setup_db):
        results = search_by_annotation("@TransCode", scope="METHOD")
        assert len(results) == 2

    def test_no_results(self, setup_db):
        results = search_by_annotation("NonExistent")
        assert len(results) == 0


class TestValueFilter:
    def test_exact_value(self, setup_db):
        results = search_by_annotation("TransCode", value="LN_LOAN_APPLY", scope="METHOD")
        assert len(results) == 1
        assert results[0]["fqn"] == "com.bank.controller.LoanController.apply"

    def test_value_no_match(self, setup_db):
        results = search_by_annotation("TransCode", value="NONEXISTENT", scope="METHOD")
        assert len(results) == 0

    def test_wildcard_value(self, setup_db):
        results = search_by_annotation("TransCode", value="LN_*", scope="METHOD")
        assert len(results) == 2

    def test_question_mark_wildcard(self, setup_db):
        results = search_by_annotation("TransCode", value="LN_LOAN_APPL?", scope="METHOD")
        assert len(results) == 1
        assert results[0]["annotation_params"]["value"] == "LN_LOAN_APPLY"


class TestScopeFilter:
    def test_method_scope(self, setup_db):
        results = search_by_annotation("TransCode", scope="METHOD")
        assert all(r["type"] == "METHOD" for r in results)

    def test_class_scope(self, setup_db):
        results = search_by_annotation("Service", scope="CLASS")
        assert len(results) == 1
        assert results[0]["type"] == "CLASS"

    def test_empty_scope_returns_all(self, setup_db):
        results = search_by_annotation("TransCode", scope="")
        assert len(results) == 2


class TestPagination:
    def test_limit(self, setup_db):
        results = search_by_annotation("TransCode", scope="METHOD", limit=1)
        assert len(results) == 1

    def test_offset(self, setup_db):
        all_results = search_by_annotation("TransCode", scope="METHOD", limit=100)
        offset_results = search_by_annotation("TransCode", scope="METHOD", limit=100, offset=1)
        assert len(offset_results) == len(all_results) - 1

    def test_limit_cap(self, setup_db):
        # Limit should be capped at 500
        results = search_by_annotation("TransCode", scope="METHOD", limit=9999)
        assert len(results) <= 500


class TestResultFields:
    def test_result_contains_all_fields(self, setup_db):
        results = search_by_annotation("TransCode", value="LN_LOAN_APPLY", scope="METHOD")
        assert len(results) == 1
        r = results[0]
        assert "fqn" in r
        assert "type" in r
        assert "file" in r
        assert "line" in r
        assert "annotation_params" in r
        assert "method_signature" in r
        assert r["annotation_params"]["value"] == "LN_LOAN_APPLY"
        assert r["method_signature"] != ""
