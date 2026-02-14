# -*- coding: utf-8 -*-
"""SQLite DDL and initialization."""

import sqlite3
from pathlib import Path

DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS codebases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path   TEXT    NOT NULL UNIQUE,
    language    TEXT    NOT NULL DEFAULT 'java',
    name        TEXT,
    commit_hash TEXT,
    last_indexed_at TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    codebase_id  INTEGER NOT NULL REFERENCES codebases(id) ON DELETE CASCADE,
    path         TEXT    NOT NULL,
    content_hash TEXT,
    language     TEXT,
    line_count   INTEGER DEFAULT 0,
    UNIQUE(codebase_id, path)
);

CREATE INDEX IF NOT EXISTS idx_files_codebase ON files(codebase_id);

CREATE TABLE IF NOT EXISTS symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    fqn         TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    symbol_type TEXT    NOT NULL,   -- CLASS, INTERFACE, ENUM, METHOD, FIELD, CONSTRUCTOR
    line_start  INTEGER NOT NULL,
    line_end    INTEGER,
    signature   TEXT,
    parent_fqn  TEXT,
    visibility  TEXT    DEFAULT 'public'
);

CREATE INDEX IF NOT EXISTS idx_symbols_fqn ON symbols(fqn);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(symbol_type);
CREATE INDEX IF NOT EXISTS idx_symbols_parent ON symbols(parent_fqn);

-- FTS5 virtual table for full-text search on symbols
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, fqn, signature,
    content='symbols',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, fqn, signature)
    VALUES (new.id, new.name, new.fqn, new.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, fqn, signature)
    VALUES ('delete', old.id, old.name, old.fqn, old.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, fqn, signature)
    VALUES ('delete', old.id, old.name, old.fqn, old.signature);
    INSERT INTO symbols_fts(rowid, name, fqn, signature)
    VALUES (new.id, new.name, new.fqn, new.signature);
END;

CREATE TABLE IF NOT EXISTS call_edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_fqn  TEXT    NOT NULL,
    callee_fqn  TEXT    NOT NULL,
    call_type   TEXT    DEFAULT 'internal',  -- internal, external
    line        INTEGER,
    confidence  REAL    DEFAULT 0.5
);

CREATE INDEX IF NOT EXISTS idx_call_caller ON call_edges(caller_fqn);
CREATE INDEX IF NOT EXISTS idx_call_callee ON call_edges(callee_fqn);

CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_fqn      TEXT    NOT NULL,
    annotation_name TEXT    NOT NULL,
    scope           TEXT    DEFAULT 'METHOD',  -- CLASS, METHOD, FIELD
    params_json     TEXT    DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_annot_name ON annotations(annotation_name);
CREATE INDEX IF NOT EXISTS idx_annot_symbol ON annotations(symbol_fqn);

CREATE TABLE IF NOT EXISTS imports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    import_path TEXT    NOT NULL,
    import_type TEXT    DEFAULT 'single'  -- single, wildcard, static
);

CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_id);
"""


def init_db(db_path: str) -> None:
    """Create tables if not exist."""
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)
    conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get a connection with row factory."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
