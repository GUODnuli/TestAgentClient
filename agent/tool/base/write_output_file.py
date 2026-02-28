# -*- coding: utf-8 -*-
"""
write_output_file — 将可交付文件写入用户下载目录

工厂函数方式，调用方在 coordinator_main.py 中绑定 user_id、conversation_id、output_dir。
"""
import json
from pathlib import Path

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


def make_write_output_file(user_id: str, conversation_id: str, output_dir: str):
    """返回绑定了路径上下文的 write_output_file 工具函数"""

    def _resp(data: dict) -> ToolResponse:
        return ToolResponse(content=[TextBlock(type="text", text=json.dumps(data, ensure_ascii=False))])

    def write_output_file(filename: str, content: str) -> ToolResponse:
        """
        Write a deliverable file to the output directory for user download.
        Use this tool when the user expects a downloadable file (JSON, CSV, Markdown, etc.).
        Only use for final deliverables — not intermediate data.

        Args:
            filename: File name (e.g. "test_cases.json", "report.md")
            content: Text content to write

        Returns:
            ToolResponse with JSON containing keys: status, file_path, bytes_written
        """
        if not output_dir:
            return _resp({"status": "error", "error": "output_dir not configured"})
        if not user_id or not conversation_id:
            return _resp({"status": "error", "error": "user_id / conversation_id not set"})

        # 路径安全：filename 不能包含路径分隔符或 ..
        safe_name = Path(filename).name
        if not safe_name:
            return _resp({"status": "error", "error": "invalid filename"})

        # 目标目录: {output_dir}/{user_id}/{conversation_id}/
        target_dir = Path(output_dir) / user_id / conversation_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / safe_name

        # 路径安全检查：确保最终路径仍在 target_dir 内
        resolved = target_path.resolve()
        base_resolved = target_dir.resolve()
        if not str(resolved).startswith(str(base_resolved)):
            return _resp({"status": "error", "error": "path traversal detected"})

        target_path.write_text(content, encoding="utf-8")
        bytes_written = len(content.encode("utf-8"))

        return _resp({
            "status": "ok",
            "file_path": str(target_path),
            "bytes_written": bytes_written,
        })

    return write_output_file
