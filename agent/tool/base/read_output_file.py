# -*- coding: utf-8 -*-
"""
read_output_file / list_output_files — 读取用户输出目录中的产物文件

与 write_output_file 完全对称：同样通过工厂函数绑定 user_id、conversation_id、output_dir，
路径规则与写入侧一致，防路径穿越校验同等严格。

主要用途：
  - Orchestrator 在 Phase 4 调用 list_output_files() 核查批次文件是否齐全
  - Orchestrator / reporter 调用 read_output_file() 读取批次产物进行合并
"""
import json
from pathlib import Path

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


def make_read_output_file(user_id: str, conversation_id: str, output_dir: str):
    """返回绑定了路径上下文的 (read_output_file, list_output_files) 工具函数元组"""

    def _resp(data: dict) -> ToolResponse:
        return ToolResponse(content=[TextBlock(type="text", text=json.dumps(data, ensure_ascii=False))])

    def _target_dir() -> Path:
        return Path(output_dir) / user_id / conversation_id

    def read_output_file(filename: str) -> ToolResponse:
        """
        Read a previously generated file from the output directory.

        Use this to verify the content of files written by write_output_file,
        or to read batch results before merging them into a final report.
        Do NOT use this for workspace files — only for files in the output directory.

        Args:
            filename: File name only, e.g. "cases_batch_1.json" or "report.md".
                      Must not contain path separators or "..".

        Returns:
            ToolResponse with JSON:
                {"status": "ok",    "content": "<file text>", "bytes": N}
                {"status": "error", "error":   "<reason>"}
        """
        if not output_dir or not user_id or not conversation_id:
            return _resp({"status": "error", "error": "output context not configured"})

        safe_name = Path(filename).name
        if not safe_name:
            return _resp({"status": "error", "error": "invalid filename"})

        target_dir = _target_dir()
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

    def list_output_files() -> ToolResponse:
        """
        List all files in the current session's output directory.

        Call this in Phase 4 to verify all expected batch files have been generated
        before merging or reporting. Files are sorted by name.

        Returns:
            ToolResponse with JSON:
                {"status": "ok", "files": [{"name": "cases_batch_1.json", "bytes": 2048}, ...]}
                {"status": "ok", "files": []}  — if directory is empty or does not exist
        """
        if not output_dir or not user_id or not conversation_id:
            return _resp({"status": "error", "error": "output context not configured"})

        target_dir = _target_dir()
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

    return read_output_file, list_output_files
