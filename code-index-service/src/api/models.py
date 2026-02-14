# -*- coding: utf-8 -*-
"""Pydantic request/response models for the API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Codebase management ──

class CodebaseCreate(BaseModel):
    root_path: str = Field(..., description="Absolute path to codebase root inside the container")
    language: str = Field(default="java", description="Primary language")
    name: Optional[str] = Field(default=None, description="Human-readable name")


class CodebaseInfo(BaseModel):
    id: int
    root_path: str
    language: str
    name: Optional[str] = None
    commit_hash: Optional[str] = None
    last_indexed_at: Optional[str] = None
    file_count: int = 0
    symbol_count: int = 0


class IndexStatus(BaseModel):
    codebase_id: int
    status: str  # idle | indexing | done | error
    progress: float = 0.0  # 0.0 ~ 1.0
    message: str = ""
    files_total: int = 0
    files_done: int = 0


# ── Query models ──

class SymbolResult(BaseModel):
    fqn: str
    name: str
    type: str
    file: str
    line: int
    signature: str = ""
    score: float = 1.0


class CallEdge(BaseModel):
    target: str
    type: str = "internal"  # internal | external
    line: Optional[int] = None
    protocol: Optional[str] = None
    service_id: Optional[str] = None


class CallChainNode(BaseModel):
    depth: int
    fqn: str
    layer: str = ""
    calls: List[CallEdge] = []
    sql_id: Optional[str] = None


class CallChainResponse(BaseModel):
    status: str = "success"
    entry_point: str = ""
    direction: str = "downstream"
    max_depth: int = 5
    chain: List[CallChainNode] = []
    external_calls: List[Dict[str, Any]] = []


class AnnotationMatch(BaseModel):
    fqn: str
    type: str
    file: str
    line: int
    annotation_params: Dict[str, Any] = {}
    method_signature: str = ""


class SourceResult(BaseModel):
    fqn: str
    file: str = ""
    line_range: List[int] = []
    signature: str = ""
    annotations: List[str] = []
    source: str = ""
    byte_size: int = 0
    truncated: bool = False


class SemanticSearchRequest(BaseModel):
    query: str
    codebase_id: Optional[int] = None
    limit: int = 10


class SemanticSearchResult(BaseModel):
    fqn: str
    file: str
    line: int = 0
    snippet: str = ""
    score: float = 0.0
