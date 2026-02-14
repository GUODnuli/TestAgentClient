# -*- coding: utf-8 -*-
"""Call chain query using BFS/DFS on call_edges table."""

from collections import deque
from typing import Any, Dict, List, Optional, Set

from src.config import SQLITE_DB_PATH
from src.storage.schema import get_connection


# Heuristic layer detection based on package/class naming conventions
_LAYER_PATTERNS = [
    ("DAO", ["mapper", "dao", "repository"]),
    ("BS", ["service", "biz", "business"]),
    ("UCC", ["controller", "ucc", "facade", "handler", "resource"]),
    ("UTIL", ["util", "helper", "common"]),
]

_VALID_DIRECTIONS = {"downstream", "upstream"}
_VALID_MODES = {"bfs", "dfs"}


def query_call_chain(
    fqn: str,
    direction: str = "downstream",
    depth: int = 5,
    include_external: bool = False,
    min_confidence: float = 0.0,
    mode: str = "bfs",
) -> Dict[str, Any]:
    """Traverse the call graph starting from fqn.

    Args:
        fqn: Starting fully-qualified name.
        direction: "downstream" (who does fqn call) or "upstream" (who calls fqn).
        depth: Maximum traversal depth (capped at 20).
        include_external: Whether to include external service calls.
        min_confidence: Minimum edge confidence to include (0.0-1.0).
        mode: Traversal mode, "bfs" (breadth-first) or "dfs" (depth-first).

    Returns:
        Dict with chain, external_calls, direction, max_depth.
    """
    # Validate inputs
    if direction not in _VALID_DIRECTIONS:
        return {
            "direction": direction,
            "max_depth": depth,
            "chain": [],
            "external_calls": [],
            "error": f"Invalid direction '{direction}', must be one of: {_VALID_DIRECTIONS}",
        }

    if mode not in _VALID_MODES:
        mode = "bfs"

    depth = min(depth, 20)
    min_confidence = max(0.0, min(1.0, min_confidence))

    conn = get_connection(str(SQLITE_DB_PATH))
    try:
        chain: List[Dict] = []
        external_calls: List[Dict] = []
        visited: Set[str] = set()
        # Use deque for both BFS (popleft) and DFS (pop)
        stack: deque = deque()
        stack.append((fqn, 0))
        visited.add(fqn)

        while stack:
            current_fqn, current_depth = stack.popleft() if mode == "bfs" else stack.pop()
            if current_depth > depth:
                continue

            edges = _get_edges(conn, current_fqn, direction, min_confidence)

            calls = []
            for edge in edges:
                target = edge["callee_fqn"] if direction == "downstream" else edge["caller_fqn"]
                call_entry: Dict[str, Any] = {
                    "target": target,
                    "type": edge["call_type"],
                    "line": edge["line"],
                    "confidence": edge["confidence"],
                }

                if edge["call_type"] == "external":
                    external_calls.append({
                        "fqn": target,
                        "protocol": "",
                        "service_id": "",
                    })
                    if not include_external:
                        continue

                calls.append(call_entry)

                if target not in visited and current_depth + 1 <= depth:
                    visited.add(target)
                    stack.append((target, current_depth + 1))

            node: Dict[str, Any] = {
                "depth": current_depth,
                "fqn": current_fqn,
                "layer": _detect_layer(current_fqn),
                "calls": calls,
            }

            # Check if this is a DAO layer with SQL mapping
            if node["layer"] == "DAO":
                method_name = current_fqn.rsplit(".", 1)[-1] if "." in current_fqn else ""
                if method_name:
                    node["sql_id"] = method_name

            chain.append(node)

        # Sort chain by depth for consistent output
        chain.sort(key=lambda n: n["depth"])

        return {
            "direction": direction,
            "max_depth": depth,
            "chain": chain,
            "external_calls": external_calls if include_external else [],
        }
    finally:
        conn.close()


def _get_edges(conn, fqn: str, direction: str, min_confidence: float) -> List[Dict]:
    """Get edges in the specified direction, filtered by confidence."""
    if direction == "downstream":
        query = "SELECT callee_fqn, caller_fqn, call_type, line, confidence FROM call_edges WHERE caller_fqn = ? AND confidence >= ? ORDER BY line"
    else:
        query = "SELECT callee_fqn, caller_fqn, call_type, line, confidence FROM call_edges WHERE callee_fqn = ? AND confidence >= ? ORDER BY line"

    rows = conn.execute(query, (fqn, min_confidence)).fetchall()
    return [dict(r) for r in rows]


def _detect_layer(fqn: str) -> str:
    fqn_lower = fqn.lower()
    for layer, keywords in _LAYER_PATTERNS:
        if any(kw in fqn_lower for kw in keywords):
            return layer
    return ""
