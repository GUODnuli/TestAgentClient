# -*- coding: utf-8 -*-
"""Shared test fixtures."""

import os
import tempfile
from pathlib import Path

import pytest

from src.storage.schema import init_db

FIXTURES_DIR = Path(__file__).parent / "fixtures"
JAVA_FIXTURES_DIR = FIXTURES_DIR / "java"


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def java_fixture_dir():
    """Return path to Java fixture files."""
    return str(JAVA_FIXTURES_DIR)
