# -*- coding: utf-8 -*-
"""Symbol search using FTS5 + LIKE fallback."""

import re
from typing import Dict, List, Optional

from src.config import SQLITE_DB_PATH
from src.storage.schema import get_connection


def search_symbols(
    pattern: str,
    symbol_type: str = "",
    language: str = "java",
    limit: int = 20,
    codebase_id: Optional[int] = None,
) -> List[Dict]:
    """Search symbols by pattern with optional type/language filter.

    Supports wildcards: * -> %, ? -> _
    Uses FTS5 for prefix/token matches, falls back to LIKE for wildcard patterns.
    """
    conn = get_connection(str(SQLITE_DB_PATH))
    try:
        results = []

        # Determine search strategy
        has_wildcards = "*" in pattern or "?" in pattern

        if has_wildcards:
            results = _like_search(conn, pattern, symbol_type, language, limit, codebase_id)
        else:
            # Try FTS5 first, then exact LIKE
            results = _fts_search(conn, pattern, symbol_type, language, limit, codebase_id)
            if not results:
                results = _like_search(conn, f"*{pattern}*", symbol_type, language, limit, codebase_id)

        return results
    finally:
        conn.close()


def _fts_search(
    conn, pattern: str, symbol_type: str, language: str, limit: int, codebase_id: Optional[int]
) -> List[Dict]:
    """Full-text search using FTS5."""
    # FTS5 query: quote the pattern for phrase match, or use prefix match
    fts_pattern = f'"{pattern}"' if " " not in pattern else pattern

    query = """
        SELECT s.fqn, s.name, s.symbol_type, f.path as file, s.line_start as line,
               s.signature, rank
        FROM symbols_fts fts
        JOIN symbols s ON fts.rowid = s.id
        JOIN files f ON s.file_id = f.id
        WHERE symbols_fts MATCH ?
    """
    params: list = [fts_pattern]

    if symbol_type:
        query += " AND s.symbol_type = ?"
        params.append(symbol_type.upper())

    if codebase_id is not None:
        query += " AND f.codebase_id = ?"
        params.append(codebase_id)

    query += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [
        {
            "fqn": r["fqn"],
            "name": r["name"],
            "type": r["symbol_type"],
            "file": r["file"],
            "line": r["line"],
            "signature": r["signature"] or "",
            "score": round(1.0 / (1.0 + abs(r["rank"])), 2) if r["rank"] else 0.5,
        }
        for r in rows
    ]


def _like_search(
    conn, pattern: str, symbol_type: str, language: str, limit: int, codebase_id: Optional[int]
) -> List[Dict]:
    """LIKE-based wildcard search."""
    # Convert wildcards: * -> %, ? -> _
    like_pattern = pattern.replace("*", "%").replace("?", "_")

    query = """
        SELECT s.fqn, s.name, s.symbol_type, f.path as file, s.line_start as line, s.signature
        FROM symbols s
        JOIN files f ON s.file_id = f.id
        WHERE (s.name LIKE ? OR s.fqn LIKE ?)
    """
    params: list = [like_pattern, like_pattern]

    if symbol_type:
        query += " AND s.symbol_type = ?"
        params.append(symbol_type.upper())

    if codebase_id is not None:
        query += " AND f.codebase_id = ?"
        params.append(codebase_id)

    query += " ORDER BY s.name LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    # Compute simple relevance score
    clean = pattern.replace("*", "").replace("?", "").lower()
    return [
        {
            "fqn": r["fqn"],
            "name": r["name"],
            "type": r["symbol_type"],
            "file": r["file"],
            "line": r["line"],
            "signature": r["signature"] or "",
            "score": _score(r["name"], clean),
        }
        for r in rows
    ]


def _score(name: str, query: str) -> float:
    """Simple relevance score."""
    nl = name.lower()
    ql = query.lower()
    if nl == ql:
        return 1.0
    if nl.startswith(ql):
        return 0.9
    if ql in nl:
        return 0.7
    return 0.5
