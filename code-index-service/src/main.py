# -*- coding: utf-8 -*-
"""FastAPI entry point for Code Index Service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import SQLITE_DB_PATH
from src.storage.schema import init_db
from src.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db(str(SQLITE_DB_PATH))
    logger.info("Code Index Service started, DB at %s", SQLITE_DB_PATH)
    yield
    logger.info("Code Index Service shutting down")


app = FastAPI(
    title="Code Index Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "code-index-service"}


if __name__ == "__main__":
    import uvicorn
    from src.config import HOST, PORT
    uvicorn.run("src.main:app", host=HOST, port=PORT, reload=False)
