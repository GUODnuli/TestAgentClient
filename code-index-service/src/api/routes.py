# -*- coding: utf-8 -*-
"""REST API routes for Code Index Service."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from src.api.models import (
    AnnotationMatch,
    CallChainResponse,
    CodebaseCreate,
    CodebaseInfo,
    IndexStatus,
    SemanticSearchRequest,
    SemanticSearchResult,
    SourceResult,
    SymbolResult,
)
from src.indexer.engine import get_index_status, run_index
from src.parser.registry import init_parsers
from src.query.annotation_search import search_by_annotation
from src.query.call_graph import query_call_chain
from src.query.source_reader import read_source_by_fqn
from src.query.symbol_search import search_symbols
from src.storage.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)
router = APIRouter()

# Ensure parsers are initialized
init_parsers()


# ── Codebase management ──

@router.post("/codebases", response_model=CodebaseInfo)
async def create_codebase(req: CodebaseCreate):
    store = SqliteStore()
    existing = store.get_codebase_by_path(req.root_path)
    if existing:
        return CodebaseInfo(
            id=existing["id"],
            root_path=existing["root_path"],
            language=existing["language"],
            name=existing.get("name"),
            commit_hash=existing.get("commit_hash"),
            last_indexed_at=existing.get("last_indexed_at"),
        )
    cid = store.create_codebase(req.root_path, req.language, req.name)
    return CodebaseInfo(id=cid, root_path=req.root_path, language=req.language, name=req.name)


@router.get("/codebases")
async def list_codebases():
    store = SqliteStore()
    codebases = store.list_codebases()
    results = []
    for cb in codebases:
        results.append(CodebaseInfo(
            id=cb["id"],
            root_path=cb["root_path"],
            language=cb["language"],
            name=cb.get("name"),
            commit_hash=cb.get("commit_hash"),
            last_indexed_at=cb.get("last_indexed_at"),
            file_count=store.get_file_count(cb["id"]),
            symbol_count=store.get_symbol_count(cb["id"]),
        ))
    return results


@router.delete("/codebases/{codebase_id}")
async def delete_codebase(codebase_id: int):
    store = SqliteStore()
    store.delete_codebase(codebase_id)
    return {"status": "deleted", "codebase_id": codebase_id}


# ── Indexing ──

@router.post("/codebases/{codebase_id}/index")
async def trigger_index(
    codebase_id: int,
    background_tasks: BackgroundTasks,
    force_full: bool = Query(default=False),
):
    store = SqliteStore()
    cb = store.get_codebase(codebase_id)
    if not cb:
        raise HTTPException(status_code=404, detail="Codebase not found")

    # Run in background
    background_tasks.add_task(run_index, codebase_id, force_full)
    return {"status": "indexing_started", "codebase_id": codebase_id}


@router.get("/codebases/{codebase_id}/index/status", response_model=IndexStatus)
async def index_status(codebase_id: int):
    status = get_index_status(codebase_id)
    return IndexStatus(**status)


# ── Query endpoints ──

@router.get("/query/symbols")
async def query_symbols(
    pattern: str = Query(..., description="Search pattern with wildcards * and ?"),
    symbol_type: str = Query(default="", description="CLASS, METHOD, FIELD, INTERFACE, ENUM"),
    language: str = Query(default="java"),
    limit: int = Query(default=20, le=100),
    codebase_id: Optional[int] = Query(default=None),
):
    results = search_symbols(pattern, symbol_type, language, limit, codebase_id)
    return {
        "status": "success",
        "query": {"pattern": pattern, "symbol_type": symbol_type, "language": language, "limit": limit},
        "results": results,
        "total": len(results),
        "note": "Results are from pre-built symbol index",
    }


@router.get("/query/call-chain")
async def query_call_chain_endpoint(
    fqn: str = Query(...),
    direction: str = Query(default="downstream"),
    depth: int = Query(default=5, le=20),
    include_external: bool = Query(default=False),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    mode: str = Query(default="bfs", pattern="^(bfs|dfs)$"),
):
    result = query_call_chain(fqn, direction, depth, include_external, min_confidence, mode)
    status = "error" if "error" in result else "success"
    return {
        "status": status,
        "query": {"fqn": fqn, "direction": direction, "depth": depth, "include_external": include_external},
        "entry_point": fqn,
        **result,
    }


@router.get("/query/annotations")
async def query_annotations(
    annotation: str = Query(..., description="Annotation name without @"),
    value: str = Query(default=""),
    scope: str = Query(default="METHOD"),
    codebase_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    annotation_clean = annotation.lstrip("@")
    matches = search_by_annotation(annotation_clean, value, scope, codebase_id, limit, offset)
    return {
        "status": "success",
        "query": {"annotation": f"@{annotation_clean}", "value": value, "scope": scope},
        "annotation": f"@{annotation_clean}",
        "value_filter": value,
        "matches": matches,
        "total": len(matches),
    }


@router.get("/query/source")
async def query_source(
    fqn: str = Query(...),
    include_body: bool = Query(default=True),
    max_tokens: int = Query(default=2000),
):
    result = read_source_by_fqn(fqn, include_body, max_tokens)
    return {
        "status": "success" if not result.get("error") else "error",
        "query": {"fqn": fqn, "include_body": include_body, "max_tokens": max_tokens},
        **result,
    }


@router.post("/query/semantic-search")
async def semantic_search(req: SemanticSearchRequest):
    # Phase 3 placeholder
    return {
        "status": "not_implemented",
        "message": "Semantic search will be available in Phase 3",
        "results": [],
    }
