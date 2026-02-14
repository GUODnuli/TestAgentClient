# -*- coding: utf-8 -*-
"""Read source code from mounted workspace volumes."""

from pathlib import Path
from typing import Optional, Tuple


class SourceStore:
    """Read source files from the codebase root."""

    def __init__(self, codebase_root: str):
        self.root = Path(codebase_root)

    def read_lines(self, relative_path: str, start: int, end: int) -> str:
        """Read lines [start, end] (1-based inclusive) from a file."""
        full_path = self.root / relative_path
        if not full_path.is_file():
            return ""
        lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        # Convert to 0-based indexing
        s = max(0, start - 1)
        e = min(len(lines), end)
        return "\n".join(lines[s:e])

    def read_file(self, relative_path: str) -> Optional[str]:
        full_path = self.root / relative_path
        if not full_path.is_file():
            return None
        return full_path.read_text(encoding="utf-8", errors="replace")

    def file_exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).is_file()
