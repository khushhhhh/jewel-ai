"""
Inngest durable function — 4-step jewelry image processing pipeline.

Each stage is implemented as an Inngest step.run() so failures are
isolated and retryable independently. Each step's output is persisted
to S3 (not just passed in-memory).

Pipeline:
  1. Semantic Masking (SAM2)
  2. Defect/Reflection Cleanup (Inpainting)
  3. Facet/Detail Sharpening (Real-ESRGAN)
  4. Background Generation (ControlNet-guided Diffusion)
"""

import logging

import inngest

from app.inngest.client import inngest_client
from app.database import async_session_factory
from app.models.image_asset import ImageAsset, ImageStatus
from app.services import job_service
from app.workers.masking import run_masking
from app.workers.cleaning import run_cleaning
from app.workers.upscaling import run_upscaling
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
    Orchestrate the 4-step jewelry image enhancement pipeline.

    Each step independently retryable; outputs persisted to S3 between steps.
    """
    step = ctx.step
    data = ctx.event.data
    asset_id = data["asset_id"]
    workspace_id = data["workspace_id"]
    background_preset = data["background_preset"]
    output_aspect_ratios = data.get("output_aspect_ratios", ["1:1"])
    output_resolution_tier = data.get("output_resolution_tier", "standard")

    logger.info(f"Starting pipeline for asset {asset_id}")

    # ── Step 1: Semantic Masking (SAM2) ──────────────────────
    mask_result = await step.run(
        "masking",
        _run_masking_step, asset_id, workspace_id,
    )

    # ── Step 2: Defect Cleanup (Inpainting) ──────────────────
    cleaned_result = await step.run(
        "cleaning",
        _run_cleaning_step, asset_id, workspace_id, mask_result,
    )

    # ── Step 3: Super-Resolution (Real-ESRGAN) ───────────────
    upscaled_result = await step.run(
        "upscaling",
        _run_upscaling_step,
        asset_id, workspace_id, cleaned_result, output_resolution_tier,
    )

    # ── Step 4: Background Generation (ControlNet) ───────────
    final_result = await step.run(
        "background_generation",
        _run_background_step,
        asset_id, workspace_id, upscaled_result,
        background_preset, output_aspect_ratios,
    )

    # ── Mark completed ───────────────────────────────────────
    await step.run(
        "finalize",
        _finalize, asset_id, final_result,
    )

    logger.info(f"Pipeline completed for asset {asset_id}")
    return {"asset_id": asset_id, "status": "COMPLETED", **final_result}


async def _run_masking_step(asset_id: str, workspace_id: str) -> dict:
    """Step 1 — SAM2 semantic masking."""
    async with async_session_factory() as db:
        await job_service.update_status(db, asset_id, ImageStatus.MASKING)

    result = await run_masking(asset_id, workspace_id)

    async with async_session_factory() as db:
        await job_service.update_status(
            db, asset_id, ImageStatus.MASKED,
            mask_s3_key=result.get("mask_s3_key"),
        )

    return result


async def _run_cleaning_step(
    asset_id: str, workspace_id: str, mask_result: dict,
) -> dict:
    """Step 2 — Inpainting defect cleanup."""
    async with async_session_factory() as db:
        await job_service.update_status(db, asset_id, ImageStatus.CLEANING)

    result = await run_cleaning(asset_id, workspace_id, mask_result)

    async with async_session_factory() as db:
        await job_service.update_status(
            db, asset_id, ImageStatus.CLEANING,
            cleaned_s3_key=result.get("cleaned_s3_key"),
        )

    return result


async def _run_upscaling_step(
    asset_id: str, workspace_id: str,
    cleaned_result: dict, resolution_tier: str,
) -> dict:
    """Step 3 — Real-ESRGAN super-resolution."""
    async with async_session_factory() as db:
        await job_service.update_status(db, asset_id, ImageStatus.UPSCALING)

    result = await run_upscaling(asset_id, workspace_id, cleaned_result, resolution_tier)

    async with async_session_factory() as db:
        await job_service.update_status(
            db, asset_id, ImageStatus.UPSCALING,
            upscaled_s3_key=result.get("upscaled_s3_key"),
        )

    return result


async def _run_background_step(
    asset_id: str, workspace_id: str,
    upscaled_result: dict, background_preset: str,
    output_aspect_ratios: list[str],
) -> dict:
    """Step 4 — ControlNet background generation."""
    async with async_session_factory() as db:
        await job_service.update_status(db, asset_id, ImageStatus.GENERATING_BG)

    result = await run_background_generation(
        asset_id, workspace_id, upscaled_result,
        background_preset, output_aspect_ratios,
    )

    return result


async def _finalize(asset_id: str, final_result: dict) -> dict:
    """Mark the job as completed with final artifact URLs."""
    async with async_session_factory() as db:
        await job_service.update_status(
            db, asset_id, ImageStatus.COMPLETED,
            final_s3_key=final_result.get("final_s3_key"),
            cdn_url=final_result.get("cdn_url"),
        )
    return {"status": "COMPLETED"}
