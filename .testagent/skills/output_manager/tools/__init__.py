# -*- coding: utf-8 -*-
"""
Output Manager skill tools package.

Provides read/list access to session output artifacts via OutputFileContext singleton.
Tools are dynamically loaded by the skill system based on SKILL.md configuration.
"""

from .output_files import read_output_file, list_output_files

__all__ = [
    "read_output_file",
    "list_output_files",
]
