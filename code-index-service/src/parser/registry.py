# -*- coding: utf-8 -*-
"""Parser registry - maps file extensions to language parsers."""

from typing import Dict, List, Optional
from src.parser.base import LanguageParser


class ParserRegistry:
    """Registry for language parsers, keyed by extension and language name."""

    def __init__(self):
        self._by_ext: Dict[str, LanguageParser] = {}
        self._by_lang: Dict[str, LanguageParser] = {}

    def register(self, parser: LanguageParser):
        for ext in parser.file_extensions():
            self._by_ext[ext] = parser
        self._by_lang[parser.language()] = parser

    def get_by_extension(self, ext: str) -> Optional[LanguageParser]:
        return self._by_ext.get(ext)

    def get_by_language(self, lang: str) -> Optional[LanguageParser]:
        return self._by_lang.get(lang)

    def supported_extensions(self) -> List[str]:
        return list(self._by_ext.keys())

    def supported_languages(self) -> List[str]:
        return list(self._by_lang.keys())


# Global singleton
_registry = ParserRegistry()


def get_registry() -> ParserRegistry:
    return _registry


def init_parsers():
    """Initialize and register all available parsers."""
    from src.parser.java_parser import JavaParser
    _registry.register(JavaParser())
