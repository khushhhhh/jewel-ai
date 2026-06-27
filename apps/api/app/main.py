"""
Jewel AI API — FastAPI Application Entry Point.

Production-grade jewelry image enhancement platform API.
Handles presigned uploads, credit management, and Inngest orchestration.
"""

import logging
from contextlib import asynccontextmanager

import inngest.fast_api
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import images, workspaces
from app.inngest import inngest_client, inngest_functions

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — init DB on startup."""
    logger.info("🚀 Jewel AI API starting up...")
    await init_db()
    logger.info("✅ Database tables initialized")
    yield
    logger.info("👋 Jewel AI API shutting down...")


app = FastAPI(
    title="Jewel AI API",
    description="Jewelry AI Enhancement Platform — Image Processing Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
app.include_router(images.router)
app.include_router(workspaces.router)

# ── Inngest ──────────────────────────────────────────────────
inngest.fast_api.serve(
    app,
    inngest_client,
    inngest_functions,
)


# ── Health check ─────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "jewel-ai-api"}


@app.get("/", tags=["root"])
async def root():
    return {
        "service": "Jewel AI API",
        "version": "0.1.0",
        "docs": "/docs",
    }
