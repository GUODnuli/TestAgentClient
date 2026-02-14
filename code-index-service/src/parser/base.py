# -*- coding: utf-8 -*-
"""Abstract base class for language parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedSymbol:
    fqn: str
    name: str
    symbol_type: str  # CLASS, INTERFACE, ENUM, METHOD, FIELD, CONSTRUCTOR
    line_start: int
    line_end: int
    signature: str = ""
    parent_fqn: str = ""
    visibility: str = "public"


@dataclass
class ParsedCallEdge:
    caller_fqn: str
    callee_fqn: str
    call_type: str = "internal"
    line: int = 0
    confidence: float = 0.5


@dataclass
class ParsedAnnotation:
    symbol_fqn: str
    annotation_name: str
    scope: str = "METHOD"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedImport:
    import_path: str
    import_type: str = "single"  # single, wildcard, static


@dataclass
class FileParseResult:
    symbols: List[ParsedSymbol] = field(default_factory=list)
    call_edges: List[ParsedCallEdge] = field(default_factory=list)
    annotations: List[ParsedAnnotation] = field(default_factory=list)
    imports: List[ParsedImport] = field(default_factory=list)


class LanguageParser(ABC):
    """Abstract interface for language-specific AST parsers."""

    @abstractmethod
    def language(self) -> str:
        """Return the language identifier, e.g. 'java'."""
        ...

    @abstractmethod
    def file_extensions(self) -> List[str]:
        """Return file extensions this parser handles, e.g. ['.java']."""
        ...

    @abstractmethod
    def parse_file(self, file_path: str, content: bytes, package_prefix: str = "") -> FileParseResult:
        """Parse a single file and extract symbols, calls, annotations, imports."""
        ...
