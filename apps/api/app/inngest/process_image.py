"""
Inngest durable function — 2-step jewelry image processing pipeline.

Pipeline:
  1. Claude Vision Analysis
  2. Gemini Multimodal Background Generation
"""

import logging

import inngest

from app.inngest.client import inngest_client
from app.database import async_session_factory
from app.models.image_asset import ImageAsset, ImageStatus
from app.services import job_service
from app.workers.analyzer import run_analyzer
from app.workers.background import run_background_generation

logger = logging.getLogger("uvicorn")


@inngest_client.create_function(
    fn_id="process-jewelry-image",
    trigger=inngest.TriggerEvent(event="image/process.requested"),
    retries=2,
)
async def process_jewelry_image(
    ctx: inngest.Context,
) -> dict:
    """
    Orchestrate the 2-step jewelry image enhancement pipeline.
    """
    step = ctx.step
    data = ctx.event.data
    asset_id = data["asset_id"]
    workspace_id = data["workspace_id"]
    background_preset = data["background_preset"]
    output_aspect_ratios = data.get("output_aspect_ratios", ["1:1"])
    output_resolution_tier = data.get("output_resolution_tier", "standard")

    logger.info(f"Starting pipeline for asset {asset_id}")

    # ── Stage 0: Claude Vision Analysis ──────────────────────
    analysis_result = await step.run(
        "analyzing",
        _run_analyzer_step, asset_id, workspace_id,
    )

    # ── Stage 1: Gemini Native Image Editing ─────────────────
    final_result = await step.run(
        "background_generation",
        _run_background_step,
        asset_id, workspace_id, analysis_result,
    )

    # ── Mark completed ───────────────────────────────────────
    await step.run(
        "finalize",
        _finalize, asset_id, workspace_id, final_result,
    )

    logger.info(f"Pipeline completed for asset {asset_id}")
    return {"asset_id": asset_id, "status": "COMPLETED", **final_result}


async def _run_analyzer_step(asset_id: str, workspace_id: str) -> dict:
    """Stage 0 — Claude Vision Analysis."""
    async with async_session_factory() as db:
        asset = await job_service.get_asset(db, asset_id, workspace_id)
        raw_s3_key = asset.raw_s3_key
        await job_service.update_status(db, asset_id, ImageStatus.ANALYZING)
        
    result = await run_analyzer(asset_id, workspace_id, raw_s3_key)
    
    async with async_session_factory() as db:
        db_asset = await job_service.get_asset(db, asset_id, workspace_id)
        db_asset.analysis_json = result.get("analysis_json")
        await db.commit()
        
    return result


async def _run_background_step(
    asset_id: str, workspace_id: str, analysis_result: dict,
) -> dict:
    """Stage 1 — Gemini Multimodal image-to-image generation."""
    async with async_session_factory() as db:
        await job_service.update_status(db, asset_id, ImageStatus.GENERATING_BG)
        asset = await job_service.get_asset(db, asset_id, workspace_id)
        raw_s3_key = asset.raw_s3_key

    result = await run_background_generation(
        asset_id, workspace_id, raw_s3_key, analysis_result,
    )

    return result


async def _run_background_step(
    asset_id: str, workspace_id: str,
    upscaled_result: dict, background_preset: str,
    output_aspect_ratios: list[str], analysis_result: dict,
) -> dict:
    """Step 4 — FLUX image-to-image background generation."""
    async with async_session_factory() as db:
        await job_service.update_status(db, asset_id, ImageStatus.GENERATING_BG)

    result = await run_background_generation(
        asset_id, workspace_id, upscaled_result,
        background_preset, output_aspect_ratios, analysis_result,
    )

    return result


async def _finalize(asset_id: str, workspace_id: str, final_result: dict) -> dict:
    """Mark the job as completed with final artifact URLs."""
    async with async_session_factory() as db:
        db_asset = await job_service.get_asset(db, asset_id, workspace_id)
        db_asset.variants_json = final_result.get("variants")
        await job_service.update_status(
            db, asset_id, ImageStatus.COMPLETED,
            final_s3_key=final_result.get("final_s3_key"),
            cdn_url=final_result.get("cdn_url"),
        )
    return {"status": "COMPLETED"}
