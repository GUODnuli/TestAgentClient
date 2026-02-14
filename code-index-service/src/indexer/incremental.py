# -*- coding: utf-8 -*-
"""Incremental indexing via git diff or content hash comparison."""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    path: str
    status: str  # added, modified, deleted


@dataclass
class ChangeSet:
    added: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    new_commit_hash: Optional[str] = None

    @property
    def total(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)

    @property
    def all_changed(self) -> List[str]:
        return self.added + self.modified


def detect_changes_git(root_path: str, old_commit: Optional[str] = None) -> ChangeSet:
    """Detect file changes using git diff.

    If old_commit is None, returns all tracked files as 'added' (full index).
    """
    root = Path(root_path)
    cs = ChangeSet()

    # Get current HEAD
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root), capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            cs.new_commit_hash = result.stdout.strip()
    except Exception:
        logger.warning("Failed to get git HEAD for %s", root_path)
        return cs

    if not old_commit:
        # Full index: treat all files as added
        return cs

    if old_commit == cs.new_commit_hash:
        # No changes
        return cs

    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", f"{old_commit}..{cs.new_commit_hash}"],
            cwd=str(root), capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("git diff failed: %s", result.stderr)
            return cs

        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status, path = parts[0], parts[1]
            if status.startswith("A"):
                cs.added.append(path)
            elif status.startswith("M"):
                cs.modified.append(path)
            elif status.startswith("D"):
                cs.deleted.append(path)
            elif status.startswith("R"):
                # Renamed: old\tnew
                rename_parts = path.split("\t")
                if len(rename_parts) == 2:
                    cs.deleted.append(rename_parts[0])
                    cs.added.append(rename_parts[1])

    except Exception as e:
        logger.warning("git diff failed: %s", e)

    return cs
