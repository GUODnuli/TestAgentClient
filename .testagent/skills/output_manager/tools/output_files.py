# -*- coding: utf-8 -*-
"""
output_manager skill tools — read_output_file / list_output_files

These are static tool functions (not factory closures) that obtain the session
output path from the OutputFileContext singleton initialized at startup.
An optional `directory` parameter allows reading arbitrary (non-session) paths.
"""
import json
from pathlib import Path
from typing import Optional

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock
from tool.base.output_file_context import get_output_context


def _resp(data: dict) -> ToolResponse:
    """Helper — NOT discovered by _load_skill_tools (leading underscore)."""
    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(data, ensure_ascii=False))])


def _resolve_directory(directory: str) -> tuple:
    """
    Returns (resolved_path: Path | None, error_msg: str | None).
    NOT discovered by _load_skill_tools (leading underscore).
    """
    if directory:
        return Path(directory), None
    ctx = get_output_context()
    if ctx is None:
        return None, "output context not configured and no directory provided"
    return Path(ctx.output_dir) / ctx.user_id / ctx.conversation_id, None


def read_output_file(filename: str, directory: str = "") -> ToolResponse:
    """
    Read a file from the output directory.

    Args:
        filename: File name only, e.g. "cases_batch_1.json". No path separators.
        directory: Optional path override. If empty, uses the session output
                   directory from OutputFileContext (set via --output-dir).
                   Pass an explicit path for non-downloadable intermediate files.

    Returns:
        ToolResponse with JSON:
            {"status": "ok",    "content": "<file text>", "bytes": N}
            {"status": "error", "error":   "<reason>"}
    """
    target_dir, err = _resolve_directory(directory)
    if err:
        return _resp({"status": "error", "error": err})

    safe_name = Path(filename).name
    if not safe_name:
        return _resp({"status": "error", "error": "invalid filename"})

    target_path = target_dir / safe_name

    # 路径安全校验：防止 "../" 穿越
    try:
        resolved = target_path.resolve()
        base_resolved = target_dir.resolve()
        if not str(resolved).startswith(str(base_resolved)):
            return _resp({"status": "error", "error": "path traversal detected"})
    except Exception as exc:
        return _resp({"status": "error", "error": f"path resolution failed: {exc}"})

    if not target_path.exists():
        return _resp({"status": "error", "error": f"file not found: {safe_name}"})

    try:
        content = target_path.read_text(encoding="utf-8")
    except Exception as exc:
        return _resp({"status": "error", "error": f"read failed: {exc}"})

    return _resp({"status": "ok", "content": content, "bytes": len(content.encode("utf-8"))})


def list_output_files(directory: str = "") -> ToolResponse:
    """
    List files in the output directory.

    Args:
        directory: Optional path override. If empty, uses the session output
                   directory from OutputFileContext (set via --output-dir).
                   Pass an explicit path for non-downloadable intermediate files.

    Returns:
        ToolResponse with JSON:
            {"status": "ok", "files": [{"name": "cases_batch_1.json", "bytes": 2048}, ...]}
            {"status": "ok", "files": []}  — if directory is empty or does not exist
            {"status": "error", "error": "<reason>"}
    """
    target_dir, err = _resolve_directory(directory)
    if err:
        return _resp({"status": "error", "error": err})

    if not target_dir.exists():
        return _resp({"status": "ok", "files": []})

    try:
        files = [
            {"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(target_dir.iterdir())
            if p.is_file()
        ]
    except Exception as exc:
        return _resp({"status": "error", "error": f"list failed: {exc}"})

    return _resp({"status": "ok", "files": files})
