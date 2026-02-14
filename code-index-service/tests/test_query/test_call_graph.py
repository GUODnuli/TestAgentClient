# -*- coding: utf-8 -*-
"""Tests for call graph query module."""

import pytest

from src.storage.schema import init_db
from src.storage.sqlite_store import SqliteStore
from src.query.call_graph import query_call_chain, _detect_layer


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Set up a test DB with sample call edges."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    import src.query.call_graph as cg
    cg.get_connection = lambda path: __import__("src.storage.schema", fromlist=["get_connection"]).get_connection(db_path)

    store = SqliteStore(db_path)
    cid = store.create_codebase("/workspace", "java")
    fid = store.upsert_file(cid, "Test.java", "h1", "java", 100)

    # Build a call graph: Controller -> Service -> Mapper
    store.insert_call_edges_batch([
        {"caller_fqn": "com.bank.controller.LoanController.apply",
         "callee_fqn": "com.bank.service.LoanService.submit",
         "call_type": "internal", "line": 20, "confidence": 0.8},
        {"caller_fqn": "com.bank.service.LoanService.submit",
         "callee_fqn": "com.bank.mapper.LoanMapper.insert",
         "call_type": "internal", "line": 45, "confidence": 0.7},
        {"caller_fqn": "com.bank.service.LoanService.submit",
         "callee_fqn": "com.bank.credit.CreditService.query",
         "call_type": "external", "line": 50, "confidence": 0.6},
        # Low confidence edge
        {"caller_fqn": "com.bank.service.LoanService.submit",
         "callee_fqn": "com.bank.util.Logger.info",
         "call_type": "internal", "line": 42, "confidence": 0.2},
        # Upstream edge (who calls controller)
        {"caller_fqn": "com.bank.gateway.ApiGateway.route",
         "callee_fqn": "com.bank.controller.LoanController.apply",
         "call_type": "internal", "line": 10, "confidence": 0.5},
    ])

    yield db_path

    cg.get_connection = lambda path: __import__("src.storage.schema", fromlist=["get_connection"]).get_connection(path)


class TestCallChainDownstream:
    def test_basic_downstream(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream", depth=5)
        assert result["direction"] == "downstream"
        assert len(result["chain"]) >= 2
        # First node should be the entry point
        assert result["chain"][0]["fqn"] == "com.bank.controller.LoanController.apply"

    def test_depth_limit(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream", depth=0)
        # Depth 0: only the root node, but its calls are still listed (just not followed)
        assert len(result["chain"]) == 1
        assert result["chain"][0]["fqn"] == "com.bank.controller.LoanController.apply"

    def test_depth_1(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream", depth=1)
        fqns = {n["fqn"] for n in result["chain"]}
        assert "com.bank.controller.LoanController.apply" in fqns
        assert "com.bank.service.LoanService.submit" in fqns

    def test_full_chain(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream", depth=5)
        fqns = {n["fqn"] for n in result["chain"]}
        assert "com.bank.controller.LoanController.apply" in fqns
        assert "com.bank.service.LoanService.submit" in fqns
        assert "com.bank.mapper.LoanMapper.insert" in fqns

    def test_external_excluded_by_default(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream", depth=5)
        assert result["external_calls"] == []
        # external edge should not appear in calls
        for node in result["chain"]:
            for call in node.get("calls", []):
                assert call["type"] != "external"

    def test_external_included(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream",
                                  depth=5, include_external=True)
        assert len(result["external_calls"]) >= 1
        ext_fqns = {e["fqn"] for e in result["external_calls"]}
        assert "com.bank.credit.CreditService.query" in ext_fqns


class TestCallChainUpstream:
    def test_upstream(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "upstream", depth=5)
        fqns = {n["fqn"] for n in result["chain"]}
        assert "com.bank.gateway.ApiGateway.route" in fqns

    def test_upstream_from_mapper(self, setup_db):
        result = query_call_chain("com.bank.mapper.LoanMapper.insert", "upstream", depth=5)
        fqns = {n["fqn"] for n in result["chain"]}
        assert "com.bank.service.LoanService.submit" in fqns


class TestConfidenceFilter:
    def test_min_confidence_filters_low(self, setup_db):
        result = query_call_chain("com.bank.service.LoanService.submit", "downstream",
                                  depth=1, min_confidence=0.5)
        # Logger.info (confidence 0.2) should be filtered out
        targets = set()
        for node in result["chain"]:
            for call in node.get("calls", []):
                targets.add(call["target"])
        assert "com.bank.util.Logger.info" not in targets
        assert "com.bank.mapper.LoanMapper.insert" in targets

    def test_min_confidence_zero_includes_all(self, setup_db):
        result = query_call_chain("com.bank.service.LoanService.submit", "downstream",
                                  depth=1, min_confidence=0.0)
        targets = set()
        for node in result["chain"]:
            for call in node.get("calls", []):
                targets.add(call["target"])
        assert "com.bank.util.Logger.info" in targets


class TestDirectionValidation:
    def test_invalid_direction(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "sideways")
        assert "error" in result


class TestTraversalMode:
    def test_bfs_mode(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream",
                                  depth=5, mode="bfs")
        # BFS: nodes should be ordered by depth
        depths = [n["depth"] for n in result["chain"]]
        assert depths == sorted(depths)

    def test_dfs_mode(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream",
                                  depth=5, mode="dfs")
        fqns = {n["fqn"] for n in result["chain"]}
        # Should still find all nodes
        assert "com.bank.service.LoanService.submit" in fqns
        assert "com.bank.mapper.LoanMapper.insert" in fqns


class TestLayerDetection:
    def test_controller_layer(self):
        assert _detect_layer("com.bank.controller.LoanController.apply") == "UCC"

    def test_service_layer(self):
        assert _detect_layer("com.bank.service.LoanService.submit") == "BS"

    def test_mapper_layer(self):
        assert _detect_layer("com.bank.mapper.LoanMapper.insert") == "DAO"

    def test_dao_sql_id(self, setup_db):
        result = query_call_chain("com.bank.controller.LoanController.apply", "downstream", depth=5)
        dao_nodes = [n for n in result["chain"] if n["layer"] == "DAO"]
        if dao_nodes:
            assert "sql_id" in dao_nodes[0]

    def test_unknown_layer(self):
        assert _detect_layer("com.bank.model.LoanRequest") == ""
