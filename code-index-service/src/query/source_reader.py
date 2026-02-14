# -*- coding: utf-8 -*-
"""FQN -> source code reader."""

from typing import Any, Dict, Optional

from src.config import SQLITE_DB_PATH
from src.storage.schema import get_connection
from src.storage.source_store import SourceStore


def read_source_by_fqn(
    fqn: str,
    include_body: bool = True,
    max_tokens: int = 2000,
) -> Dict[str, Any]:
    """Look up a symbol by FQN and read its source from disk.

    Returns a dict matching the read_method_source response format.
    """
    conn = get_connection(str(SQLITE_DB_PATH))
    try:
        row = conn.execute(
            """SELECT s.fqn, s.name, s.symbol_type, s.line_start, s.line_end,
                      s.signature, s.parent_fqn, f.path, c.root_path
               FROM symbols s
               JOIN files f ON s.file_id = f.id
               JOIN codebases c ON f.codebase_id = c.id
               WHERE s.fqn = ?""",
            (fqn,),
        ).fetchone()

        if not row:
            return {
                "fqn": fqn,
                "file": "",
                "line_range": [],
                "signature": "",
                "annotations": [],
                "source": "",
                "byte_size": 0,
                "truncated": False,
                "error": "Symbol not found",
            }

        row = dict(row)
        source_store = SourceStore(row["root_path"])
        line_start = row["line_start"]
        line_end = row["line_end"] or line_start

        if include_body:
            source = source_store.read_lines(row["path"], line_start, line_end)
        else:
            # Just read the signature line
            source = row["signature"] or source_store.read_lines(row["path"], line_start, line_start)

        # Fetch annotations for this symbol
        ann_rows = conn.execute(
            "SELECT annotation_name FROM annotations WHERE symbol_fqn = ?", (fqn,)
        ).fetchall()
        annotations = [f"@{a['annotation_name']}" for a in ann_rows]

        # Truncate if needed
        truncated = False
        byte_size = len(source.encode("utf-8"))
        # Rough token estimate: 1 token ~ 4 chars
        if len(source) > max_tokens * 4:
            source = source[: max_tokens * 4]
            truncated = True

        return {
            "fqn": fqn,
            "file": row["path"],
            "line_range": [line_start, line_end],
            "signature": row["signature"] or "",
            "annotations": annotations,
            "source": source,
            "byte_size": byte_size,
            "truncated": truncated,
        }
    finally:
        conn.close()
