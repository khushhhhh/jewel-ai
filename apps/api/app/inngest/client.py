"""Inngest client initialization."""

import logging

import inngest

from app.config import settings

inngest_client = inngest.Inngest(
    app_id="jewel-ai",
    event_key=settings.inngest_event_key,
    is_production=not settings.inngest_dev,
    logger=logging.getLogger("uvicorn"),
)
