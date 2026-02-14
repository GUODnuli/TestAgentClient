# -*- coding: utf-8 -*-
"""File discovery and language detection."""

import hashlib
from pathlib import Path
from typing import List, Tuple

from src.parser.registry import get_registry

# Directories to always skip
_SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__",
    ".idea", ".vscode", ".settings", "target", "build", "dist", "out",
    ".gradle", ".mvn", "bin",
}


def scan_files(root: str, extensions: List[str] = None) -> List[Tuple[str, str]]:
    """Scan directory for source files.

    Returns list of (relative_path, language) tuples.
    """
    root_path = Path(root)
    if extensions is None:
        extensions = get_registry().supported_extensions()

    ext_set = set(extensions)
    results: List[Tuple[str, str]] = []

    for p in root_path.rglob("*"):
        if p.is_dir():
            continue
        # Skip hidden and build directories
        parts = p.relative_to(root_path).parts
        if any(part in _SKIP_DIRS or part.startswith(".") for part in parts):
            continue
        if p.suffix in ext_set:
            lang = _ext_to_lang(p.suffix)
            rel = str(p.relative_to(root_path))
            results.append((rel, lang))

    return results


def content_hash(data: bytes) -> str:
    """SHA-256 hex digest of file content."""
    return hashlib.sha256(data).hexdigest()


def _ext_to_lang(ext: str) -> str:
    mapping = {
        ".java": "java",
        ".go": "go",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
    }
    return mapping.get(ext, "unknown")
