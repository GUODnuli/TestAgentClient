# -*- coding: utf-8 -*-
"""Lazy-load tree-sitter languages."""

from functools import lru_cache
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser


@lru_cache(maxsize=8)
def get_parser(lang: str) -> Parser:
    """Return a tree-sitter Parser for the given language."""
    language = _get_language(lang)
    parser = Parser(language)
    return parser


def _get_language(lang: str) -> Language:
    if lang == "java":
        return Language(tsjava.language())
    raise ValueError(f"Unsupported tree-sitter language: {lang}")
