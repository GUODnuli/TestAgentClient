# -*- coding: utf-8 -*-
"""Integration test: parse Java fixtures → index → query all endpoints."""

import json
import os
from pathlib import Path

import pytest

from src.storage.schema import init_db
from src.storage.sqlite_store import SqliteStore
from src.parser.java_parser import JavaParser
from src.parser.registry import ParserRegistry
from src.indexer.engine import run_index, _index_status
from src.parser.registry import init_parsers
from src.query.symbol_search import search_symbols
from src.query.call_graph import query_call_chain
from src.query.annotation_search import search_by_annotation
from src.query.source_reader import read_source_by_fqn

# Ensure parsers are registered
init_parsers()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "java"


@pytest.fixture
def indexed_db(tmp_path, monkeypatch):
    """Create DB, register codebase pointing to fixtures, and run full index."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    # Patch SQLITE_DB_PATH everywhere
    import src.config
    monkeypatch.setattr(src.config, "SQLITE_DB_PATH", tmp_path / "test.db")

    # Patch all query modules to use our test DB
    for mod_path in [
        "src.query.symbol_search",
        "src.query.call_graph",
        "src.query.annotation_search",
        "src.query.source_reader",
    ]:
        mod = __import__(mod_path, fromlist=["get_connection"])
        mod.get_connection = lambda path, _db=db_path: __import__(
            "src.storage.schema", fromlist=["get_connection"]
        ).get_connection(_db)

    # Patch SQLITE_DB_PATH in all modules that import it
    import src.indexer.engine as eng
    import src.storage.sqlite_store as ss_mod
    monkeypatch.setattr(eng, "SQLITE_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(ss_mod, "SQLITE_DB_PATH", tmp_path / "test.db")

    # Register codebase
    store = SqliteStore(db_path)
    cid = store.create_codebase(str(FIXTURES_DIR), "java", "test-fixtures")

    # Run index
    result = run_index(cid, force_full=True)
    assert result.get("status") == "done", f"Indexing failed: {result}"
    assert result["files_indexed"] >= 3
    assert result["symbols"] > 0

    return {"db_path": db_path, "codebase_id": cid, "index_result": result}


class TestIntegrationSymbolSearch:
    def test_find_class_by_name(self, indexed_db):
        results = search_symbols("LoanController", symbol_type="CLASS")
        assert len(results) >= 1
        assert any(r["name"] == "LoanController" for r in results)

    def test_find_method_by_wildcard(self, indexed_db):
        results = search_symbols("*apply*", symbol_type="METHOD")
        assert len(results) >= 1
        assert any("apply" in r["name"] for r in results)

    def test_find_interface(self, indexed_db):
        results = search_symbols("LoanMapper", symbol_type="INTERFACE")
        assert len(results) >= 1

    def test_find_service_class(self, indexed_db):
        results = search_symbols("LoanService", symbol_type="CLASS")
        assert len(results) >= 1
        r = results[0]
        assert r["fqn"] == "com.bank.loan.service.LoanService"
        assert r["file"] != ""


class TestIntegrationCallGraph:
    def test_downstream_from_controller(self, indexed_db):
        # LoanController.apply -> LoanService.submitApplication
        result = query_call_chain(
            "com.bank.loan.controller.LoanController.apply",
            direction="downstream", depth=3,
        )
        assert len(result["chain"]) >= 1
        # Check that it finds calls
        root = result["chain"][0]
        assert root["fqn"] == "com.bank.loan.controller.LoanController.apply"
        if root["calls"]:
            targets = {c["target"] for c in root["calls"]}
            # Should have resolved loanService.submitApplication via field type
            assert any("submitApplication" in t for t in targets)

    def test_upstream_to_mapper(self, indexed_db):
        # Who calls LoanMapper methods?
        result = query_call_chain(
            "com.bank.loan.mapper.LoanMapper.insertApplication",
            direction="upstream", depth=3, min_confidence=0.0,
        )
        # Should find at least the mapper node itself
        assert len(result["chain"]) >= 1

    def test_confidence_filter(self, indexed_db):
        result_all = query_call_chain(
            "com.bank.loan.controller.LoanController.apply",
            direction="downstream", depth=1, min_confidence=0.0,
        )
        result_high = query_call_chain(
            "com.bank.loan.controller.LoanController.apply",
            direction="downstream", depth=1, min_confidence=0.6,
        )
        # High confidence should have fewer or equal edges
        all_calls = sum(len(n["calls"]) for n in result_all["chain"])
        high_calls = sum(len(n["calls"]) for n in result_high["chain"])
        assert high_calls <= all_calls


class TestIntegrationAnnotations:
    def test_find_transcode(self, indexed_db):
        results = search_by_annotation("TransCode", scope="METHOD")
        assert len(results) >= 1
        fqns = {r["fqn"] for r in results}
        assert "com.bank.loan.controller.LoanController.apply" in fqns

    def test_find_transcode_with_value(self, indexed_db):
        results = search_by_annotation("TransCode", value="LN_LOAN_APPLY", scope="METHOD")
        assert len(results) >= 1
        assert results[0]["annotation_params"].get("value") == "LN_LOAN_APPLY"

    def test_find_service_annotation(self, indexed_db):
        results = search_by_annotation("Service", scope="CLASS")
        assert len(results) >= 1
        assert any("LoanService" in r["fqn"] for r in results)

    def test_find_rest_controller(self, indexed_db):
        results = search_by_annotation("RestController", scope="CLASS")
        assert len(results) >= 1

    def test_find_mapper_annotation(self, indexed_db):
        results = search_by_annotation("Mapper", scope="CLASS")
        assert len(results) >= 1


class TestIntegrationSourceReader:
    def test_read_method_source(self, indexed_db):
        result = read_source_by_fqn(
            "com.bank.loan.service.LoanService.submitApplication",
            include_body=True,
        )
        assert result["fqn"] == "com.bank.loan.service.LoanService.submitApplication"
        assert result["file"] != ""
        assert result["source"] != ""
        assert "submitApplication" in result["source"]
        assert not result["truncated"]

    def test_read_signature_only(self, indexed_db):
        result = read_source_by_fqn(
            "com.bank.loan.service.LoanService.submitApplication",
            include_body=False,
        )
        assert result["source"] != ""
        # Should be shorter than full body
        assert len(result["source"]) < 500

    def test_read_nonexistent_symbol(self, indexed_db):
        result = read_source_by_fqn("com.nonexistent.Foo.bar")
        assert result.get("error") == "Symbol not found"

    def test_read_class_source(self, indexed_db):
        result = read_source_by_fqn(
            "com.bank.loan.controller.LoanController",
            include_body=True,
        )
        assert "LoanController" in result["source"]


class TestIntegrationIndexStats:
    def test_index_summary(self, indexed_db):
        result = indexed_db["index_result"]
        assert result["symbols"] > 5  # multiple classes + methods + fields
        assert result["call_edges"] > 0
        assert result["annotations"] > 0
        assert result["elapsed_seconds"] >= 0

    def test_codebase_counts(self, indexed_db):
        store = SqliteStore(indexed_db["db_path"])
        cid = indexed_db["codebase_id"]
        assert store.get_file_count(cid) >= 3
        assert store.get_symbol_count(cid) > 5
