# -*- coding: utf-8 -*-
"""Tests for SqliteStore CRUD operations."""

import pytest

from src.storage.sqlite_store import SqliteStore
from src.storage.schema import init_db


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return SqliteStore(db_path)


class TestCodebases:
    def test_create_and_get(self, store):
        cid = store.create_codebase("/workspace/project", "java", "test-project")
        cb = store.get_codebase(cid)
        assert cb is not None
        assert cb["root_path"] == "/workspace/project"
        assert cb["language"] == "java"

    def test_list(self, store):
        store.create_codebase("/a", "java")
        store.create_codebase("/b", "go")
        codebases = store.list_codebases()
        assert len(codebases) == 2

    def test_delete(self, store):
        cid = store.create_codebase("/workspace/project", "java")
        store.delete_codebase(cid)
        assert store.get_codebase(cid) is None

    def test_get_by_path(self, store):
        store.create_codebase("/workspace/project", "java")
        cb = store.get_codebase_by_path("/workspace/project")
        assert cb is not None


class TestFiles:
    def test_upsert_and_get(self, store):
        cid = store.create_codebase("/workspace", "java")
        fid = store.upsert_file(cid, "src/Main.java", "abc123", "java", 100)
        f = store.get_file(cid, "src/Main.java")
        assert f is not None
        assert f["content_hash"] == "abc123"

    def test_upsert_updates_hash(self, store):
        cid = store.create_codebase("/workspace", "java")
        store.upsert_file(cid, "src/Main.java", "hash1", "java", 100)
        store.upsert_file(cid, "src/Main.java", "hash2", "java", 110)
        f = store.get_file(cid, "src/Main.java")
        assert f["content_hash"] == "hash2"

    def test_file_count(self, store):
        cid = store.create_codebase("/workspace", "java")
        store.upsert_file(cid, "a.java", "h1", "java", 10)
        store.upsert_file(cid, "b.java", "h2", "java", 20)
        assert store.get_file_count(cid) == 2


class TestSymbols:
    def test_insert_and_query(self, store):
        cid = store.create_codebase("/workspace", "java")
        fid = store.upsert_file(cid, "Test.java", "h1", "java", 50)
        store.insert_symbols_batch([{
            "file_id": fid,
            "fqn": "com.test.MyClass",
            "name": "MyClass",
            "symbol_type": "CLASS",
            "line_start": 1,
            "line_end": 50,
            "signature": "public class MyClass",
            "parent_fqn": "",
            "visibility": "public",
        }])
        sym = store.get_symbol_by_fqn("com.test.MyClass")
        assert sym is not None
        assert sym["name"] == "MyClass"

    def test_symbol_count(self, store):
        cid = store.create_codebase("/workspace", "java")
        fid = store.upsert_file(cid, "Test.java", "h1", "java", 50)
        store.insert_symbols_batch([
            {"file_id": fid, "fqn": "com.test.A", "name": "A", "symbol_type": "CLASS",
             "line_start": 1, "line_end": 10, "signature": "", "parent_fqn": "", "visibility": "public"},
            {"file_id": fid, "fqn": "com.test.B", "name": "B", "symbol_type": "CLASS",
             "line_start": 11, "line_end": 20, "signature": "", "parent_fqn": "", "visibility": "public"},
        ])
        assert store.get_symbol_count(cid) == 2


class TestCallEdges:
    def test_insert_and_delete(self, store):
        store.insert_call_edges_batch([{
            "caller_fqn": "com.A.foo",
            "callee_fqn": "com.B.bar",
            "call_type": "internal",
            "line": 10,
            "confidence": 0.8,
        }])
        store.delete_call_edges_by_fqns(["com.A.foo"])
        # No error means success


class TestAnnotations:
    def test_insert_and_delete(self, store):
        store.insert_annotations_batch([{
            "symbol_fqn": "com.A.foo",
            "annotation_name": "Transactional",
            "scope": "METHOD",
            "params_json": "{}",
        }])
        store.delete_annotations_by_symbol_fqns(["com.A.foo"])
