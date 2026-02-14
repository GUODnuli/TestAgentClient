# -*- coding: utf-8 -*-
"""Annotation-based symbol search."""

import json
from typing import Any, Dict, List, Optional

from src.config import SQLITE_DB_PATH
from src.storage.schema import get_connection


def search_by_annotation(
    annotation: str,
    value: str = "",
    scope: str = "METHOD",
    codebase_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """Find symbols annotated with the given annotation name.

    Args:
        annotation: name without '@', e.g. "TransCode", "RequestMapping"
        value: optional filter on annotation parameter value. Supports wildcards (* and ?).
        scope: CLASS, METHOD, FIELD, or empty string for all scopes
        codebase_id: optional filter by codebase
        limit: max results (default 100, capped at 500)
        offset: pagination offset
    """
    annotation = annotation.lstrip("@")
    limit = min(limit, 500)

    conn = get_connection(str(SQLITE_DB_PATH))
    try:
        query = """
            SELECT a.symbol_fqn, a.annotation_name, a.scope, a.params_json,
                   s.symbol_type, s.signature, s.line_start, f.path as file_path
            FROM annotations a
            LEFT JOIN symbols s ON a.symbol_fqn = s.fqn
            LEFT JOIN files f ON s.file_id = f.id
            WHERE a.annotation_name = ?
        """
        params: list = [annotation]

        if scope:
            query += " AND a.scope = ?"
            params.append(scope.upper())

        if codebase_id is not None:
            query += " AND f.codebase_id = ?"
            params.append(codebase_id)

        query += " ORDER BY a.symbol_fqn LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()

        # Prepare value filter (support wildcards)
        value_filter = None
        if value:
            value_filter = value.replace("*", "%").replace("?", "_") if ("*" in value or "?" in value) else None

        results = []
        for r in rows:
            try:
                params_dict = json.loads(r["params_json"]) if r["params_json"] else {}
            except (json.JSONDecodeError, TypeError):
                params_dict = {}

            # Apply value filter
            if value:
                matched = False
                for v in params_dict.values():
                    sv = str(v)
                    if value_filter:
                        # Wildcard match using SQL-like pattern
                        matched = _wildcard_match(sv, value)
                    else:
                        # Exact match
                        matched = sv == value
                    if matched:
                        break
                if not matched:
                    continue

            results.append({
                "fqn": r["symbol_fqn"],
                "type": r["symbol_type"] or r["scope"],
                "file": r["file_path"] or "",
                "line": r["line_start"] or 0,
                "annotation_params": params_dict,
                "method_signature": r["signature"] or "",
            })

        return results
    finally:
        conn.close()


def _wildcard_match(text: str, pattern: str) -> bool:
    """Simple wildcard matching: * matches any sequence, ? matches one char."""
    import fnmatch
    return fnmatch.fnmatch(text, pattern)
