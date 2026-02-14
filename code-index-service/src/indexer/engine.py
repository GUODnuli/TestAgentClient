# -*- coding: utf-8 -*-
"""Index orchestration engine - full and incremental indexing."""

import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.config import INDEX_WORKERS, SQLITE_DB_PATH
from src.indexer.file_scanner import content_hash, scan_files
from src.indexer.incremental import ChangeSet, detect_changes_git
from src.parser.base import FileParseResult
from src.parser.registry import get_registry
from src.storage.schema import init_db
from src.storage.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)


# Status tracking for async indexing
_index_status: Dict[int, Dict[str, Any]] = {}


def get_index_status(codebase_id: int) -> Dict[str, Any]:
    return _index_status.get(codebase_id, {
        "codebase_id": codebase_id,
        "status": "idle",
        "progress": 0.0,
        "message": "",
        "files_total": 0,
        "files_done": 0,
    })


def _update_status(codebase_id: int, **kwargs):
    if codebase_id not in _index_status:
        _index_status[codebase_id] = {
            "codebase_id": codebase_id,
            "status": "idle",
            "progress": 0.0,
            "message": "",
            "files_total": 0,
            "files_done": 0,
        }
    _index_status[codebase_id].update(kwargs)


def run_index(codebase_id: int, force_full: bool = False) -> Dict[str, Any]:
    """Run indexing for a codebase (synchronous).

    Returns summary dict.
    """
    store = SqliteStore()
    cb = store.get_codebase(codebase_id)
    if not cb:
        return {"error": f"Codebase {codebase_id} not found"}

    root_path = cb["root_path"]
    language = cb["language"]
    old_commit = cb["commit_hash"]

    _update_status(codebase_id, status="indexing", progress=0.0, message="Scanning files...")

    registry = get_registry()
    parser = registry.get_by_language(language)
    if not parser:
        _update_status(codebase_id, status="error", message=f"No parser for language: {language}")
        return {"error": f"No parser for language: {language}"}

    # Detect changes
    if force_full or not old_commit:
        changeset = None  # Full index
    else:
        changeset = detect_changes_git(root_path, old_commit)
        if changeset.total == 0 and changeset.new_commit_hash == old_commit:
            _update_status(codebase_id, status="done", progress=1.0, message="No changes detected")
            return {"status": "no_changes", "commit_hash": old_commit}

    # Get files to process
    extensions = parser.file_extensions()

    if changeset:
        # Incremental: only process changed files
        files_to_process = [
            (p, language) for p in changeset.all_changed
            if any(p.endswith(ext) for ext in extensions)
        ]
        # Handle deletions
        if changeset.deleted:
            store.delete_files_by_paths(codebase_id, changeset.deleted)
            logger.info("Deleted %d files from index", len(changeset.deleted))
    else:
        # Full index: scan all
        files_to_process = scan_files(root_path, extensions)

    total_files = len(files_to_process)
    _update_status(codebase_id, files_total=total_files, message=f"Parsing {total_files} files...")
    logger.info("Indexing %d files for codebase %d (%s)", total_files, codebase_id, root_path)

    if total_files == 0:
        new_hash = changeset.new_commit_hash if changeset else _get_head_hash(root_path)
        if new_hash:
            store.update_codebase_index_state(codebase_id, new_hash)
        _update_status(codebase_id, status="done", progress=1.0, message="No files to index")
        return {"status": "done", "files_indexed": 0, "commit_hash": new_hash}

    # Parse and store
    start_time = time.time()
    files_done = 0
    total_symbols = 0
    total_edges = 0
    total_annotations = 0

    for rel_path, lang in files_to_process:
        full_path = Path(root_path) / rel_path
        if not full_path.is_file():
            files_done += 1
            continue

        try:
            raw = full_path.read_bytes()
            file_hash = content_hash(raw)
            line_count = raw.count(b"\n") + 1

            # Check if file unchanged (by hash)
            existing = store.get_file(codebase_id, rel_path)
            if existing and existing["content_hash"] == file_hash and not force_full:
                files_done += 1
                _update_status(codebase_id, files_done=files_done,
                               progress=files_done / total_files)
                continue

            # Parse
            parse_result = parser.parse_file(str(full_path), raw)

            # Upsert file record
            file_id = store.upsert_file(codebase_id, rel_path, file_hash, lang, line_count)

            # Clear old data for this file
            store.delete_symbols_by_file(file_id)
            store.delete_imports_by_file(file_id)

            # Collect FQNs for edge/annotation cleanup
            old_fqns = [s.fqn for s in parse_result.symbols]

            # Store symbols
            sym_dicts = [
                {
                    "file_id": file_id,
                    "fqn": s.fqn,
                    "name": s.name,
                    "symbol_type": s.symbol_type,
                    "line_start": s.line_start,
                    "line_end": s.line_end,
                    "signature": s.signature,
                    "parent_fqn": s.parent_fqn,
                    "visibility": s.visibility,
                }
                for s in parse_result.symbols
            ]
            store.insert_symbols_batch(sym_dicts)
            total_symbols += len(sym_dicts)

            # Store call edges (delete old first)
            if old_fqns:
                store.delete_call_edges_by_fqns(old_fqns)
                store.delete_annotations_by_symbol_fqns(old_fqns)

            edge_dicts = [
                {
                    "caller_fqn": e.caller_fqn,
                    "callee_fqn": e.callee_fqn,
                    "call_type": e.call_type,
                    "line": e.line,
                    "confidence": e.confidence,
                }
                for e in parse_result.call_edges
            ]
            store.insert_call_edges_batch(edge_dicts)
            total_edges += len(edge_dicts)

            # Store annotations
            ann_dicts = [
                {
                    "symbol_fqn": a.symbol_fqn,
                    "annotation_name": a.annotation_name,
                    "scope": a.scope,
                    "params_json": json.dumps(a.params, ensure_ascii=False),
                }
                for a in parse_result.annotations
            ]
            store.insert_annotations_batch(ann_dicts)
            total_annotations += len(ann_dicts)

            # Store imports
            imp_dicts = [
                {"file_id": file_id, "import_path": i.import_path, "import_type": i.import_type}
                for i in parse_result.imports
            ]
            store.insert_imports_batch(imp_dicts)

        except Exception:
            logger.exception("Failed to index file: %s", rel_path)

        files_done += 1
        if files_done % 100 == 0 or files_done == total_files:
            _update_status(
                codebase_id,
                files_done=files_done,
                progress=files_done / total_files,
                message=f"Parsed {files_done}/{total_files} files",
            )

    # Update commit hash
    new_hash = changeset.new_commit_hash if changeset else _get_head_hash(root_path)
    if new_hash:
        store.update_codebase_index_state(codebase_id, new_hash)

    elapsed = time.time() - start_time
    summary = {
        "status": "done",
        "files_indexed": files_done,
        "symbols": total_symbols,
        "call_edges": total_edges,
        "annotations": total_annotations,
        "elapsed_seconds": round(elapsed, 2),
        "commit_hash": new_hash,
    }

    _update_status(codebase_id, status="done", progress=1.0,
                   files_done=files_done, message=f"Done in {elapsed:.1f}s")
    logger.info("Indexing complete for codebase %d: %s", codebase_id, summary)
    return summary


def _get_head_hash(root_path: str) -> Optional[str]:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_path, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
