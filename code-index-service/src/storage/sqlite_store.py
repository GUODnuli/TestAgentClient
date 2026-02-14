# -*- coding: utf-8 -*-
"""SQLite-backed structured data store for code index."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.config import SQLITE_DB_PATH
from src.storage.schema import get_connection


class SqliteStore:
    """CRUD operations on the code index SQLite database."""

    def __init__(self, db_path: str = None):
        self._db_path = db_path or str(SQLITE_DB_PATH)

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    # ── Codebases ──

    def create_codebase(self, root_path: str, language: str = "java", name: str = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO codebases (root_path, language, name) VALUES (?, ?, ?)",
                (root_path, language, name),
            )
            return cur.lastrowid

    def get_codebase(self, codebase_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM codebases WHERE id = ?", (codebase_id,)).fetchone()
            return dict(row) if row else None

    def get_codebase_by_path(self, root_path: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM codebases WHERE root_path = ?", (root_path,)).fetchone()
            return dict(row) if row else None

    def list_codebases(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM codebases ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    def delete_codebase(self, codebase_id: int) -> bool:
        with self._conn() as conn:
            conn.execute("DELETE FROM codebases WHERE id = ?", (codebase_id,))
            return conn.total_changes > 0

    def update_codebase_index_state(self, codebase_id: int, commit_hash: str = None):
        with self._conn() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE codebases SET commit_hash = ?, last_indexed_at = ? WHERE id = ?",
                (commit_hash, now, codebase_id),
            )

    # ── Files ──

    def upsert_file(self, codebase_id: int, path: str, content_hash: str, language: str, line_count: int) -> int:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO files (codebase_id, path, content_hash, language, line_count)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(codebase_id, path) DO UPDATE SET
                       content_hash = excluded.content_hash,
                       language = excluded.language,
                       line_count = excluded.line_count""",
                (codebase_id, path, content_hash, language, line_count),
            )
            row = conn.execute(
                "SELECT id FROM files WHERE codebase_id = ? AND path = ?",
                (codebase_id, path),
            ).fetchone()
            return row["id"]

    def get_file(self, codebase_id: int, path: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE codebase_id = ? AND path = ?",
                (codebase_id, path),
            ).fetchone()
            return dict(row) if row else None

    def delete_file(self, file_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def delete_files_by_paths(self, codebase_id: int, paths: List[str]):
        with self._conn() as conn:
            conn.executemany(
                "DELETE FROM files WHERE codebase_id = ? AND path = ?",
                [(codebase_id, p) for p in paths],
            )

    def get_file_count(self, codebase_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM files WHERE codebase_id = ?", (codebase_id,)
            ).fetchone()
            return row["cnt"]

    # ── Symbols ──

    def insert_symbols_batch(self, symbols: List[Dict]):
        """Batch insert symbols. Each dict must have: file_id, fqn, name, symbol_type, line_start, line_end, signature, parent_fqn, visibility."""
        if not symbols:
            return
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO symbols (file_id, fqn, name, symbol_type, line_start, line_end, signature, parent_fqn, visibility)
                   VALUES (:file_id, :fqn, :name, :symbol_type, :line_start, :line_end, :signature, :parent_fqn, :visibility)""",
                symbols,
            )

    def delete_symbols_by_file(self, file_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))

    def get_symbol_by_fqn(self, fqn: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT s.*, f.path as file_path, f.codebase_id
                   FROM symbols s JOIN files f ON s.file_id = f.id
                   WHERE s.fqn = ?""",
                (fqn,),
            ).fetchone()
            return dict(row) if row else None

    def get_symbol_count(self, codebase_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM symbols s
                   JOIN files f ON s.file_id = f.id
                   WHERE f.codebase_id = ?""",
                (codebase_id,),
            ).fetchone()
            return row["cnt"]

    # ── Call Edges ──

    def insert_call_edges_batch(self, edges: List[Dict]):
        """Batch insert call edges. Each dict: caller_fqn, callee_fqn, call_type, line, confidence."""
        if not edges:
            return
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO call_edges (caller_fqn, callee_fqn, call_type, line, confidence)
                   VALUES (:caller_fqn, :callee_fqn, :call_type, :line, :confidence)""",
                edges,
            )

    def delete_call_edges_by_caller(self, caller_fqn: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM call_edges WHERE caller_fqn = ?", (caller_fqn,))

    def delete_call_edges_by_fqns(self, fqns: List[str]):
        """Delete all edges where caller is in the given FQN list."""
        if not fqns:
            return
        with self._conn() as conn:
            placeholders = ",".join("?" for _ in fqns)
            conn.execute(f"DELETE FROM call_edges WHERE caller_fqn IN ({placeholders})", fqns)

    # ── Annotations ──

    def insert_annotations_batch(self, annotations: List[Dict]):
        """Batch insert annotations. Each dict: symbol_fqn, annotation_name, scope, params_json."""
        if not annotations:
            return
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO annotations (symbol_fqn, annotation_name, scope, params_json)
                   VALUES (:symbol_fqn, :annotation_name, :scope, :params_json)""",
                annotations,
            )

    def delete_annotations_by_symbol_fqns(self, fqns: List[str]):
        if not fqns:
            return
        with self._conn() as conn:
            placeholders = ",".join("?" for _ in fqns)
            conn.execute(f"DELETE FROM annotations WHERE symbol_fqn IN ({placeholders})", fqns)

    # ── Imports ──

    def insert_imports_batch(self, imports: List[Dict]):
        """Batch insert imports. Each dict: file_id, import_path, import_type."""
        if not imports:
            return
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO imports (file_id, import_path, import_type)
                   VALUES (:file_id, :import_path, :import_type)""",
                imports,
            )

    def delete_imports_by_file(self, file_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM imports WHERE file_id = ?", (file_id,))

    def get_imports_for_file(self, file_id: int) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM imports WHERE file_id = ?", (file_id,)
            ).fetchall()
            return [dict(r) for r in rows]
