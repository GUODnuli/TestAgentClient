# -*- coding: utf-8 -*-
"""Configuration from environment variables."""

import os
from pathlib import Path


STORAGE_PATH = Path(os.environ.get("STORAGE_PATH", "/data"))
SQLITE_DB_PATH = STORAGE_PATH / "code_index.db"
CHROMADB_PATH = STORAGE_PATH / "chromadb"

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

# Max workers for parallel file parsing
INDEX_WORKERS = int(os.environ.get("INDEX_WORKERS", "4"))

# Default workspace mount point
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
