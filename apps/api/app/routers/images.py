"""
Image API Router — upload, process, and status endpoints.

Implements the exact API contracts from the system architecture blueprint.
"""

from math import ceil
from uuid import uuid4, UUID

import inngest
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_workspace, WorkspaceContext
from app.models.image_asset import ImageAsset, ImageStatus
from app.models.credit import CreditBalance
from app.schemas.upload import UploadRequest, UploadResponse
from app.schemas.process import ProcessRequest, ProcessResponse
from app.schemas.status import StatusResponse, StageProgress
from app.services.s3_service import generate_presigned_put_url, s3_client
from app.config import settings
from app.services.credit_service import (
    calculate_credit_cost,
    check_balance,
    debit_credits,
)
from app.inngest.client import inngest_client

router = APIRouter(prefix="/api/v1/images", tags=["images"])


# ═══════════════════════════════════════════════════════════════
# POST /api/v1/images/upload
# ═══════════════════════════════════════════════════════════════

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def create_upload(
    payload: UploadRequest,
    workspace: WorkspaceContext = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a presigned S3 PUT URL for direct browser upload.

    Does NOT receive file bytes — the browser uploads directly to S3,
    bypassing the API tier entirely. This avoids holding multipart
    streams in memory/disk on the API tier.
    """
    asset_id = uuid4()
    s3_key = f"raw-uploads/{workspace.id}/{asset_id}/{payload.filename}"

    presigned_url = generate_presigned_put_url(
        s3_key=s3_key,
        content_type=payload.content_type,
    )

    asset = ImageAsset(
        id=asset_id,
        workspace_id=workspace.id,
        uploaded_by=workspace.user_id,
        raw_s3_key=s3_key,
        raw_file_size_bytes=payload.file_size_bytes,
        status=ImageStatus.UPLOADED,
    )
    db.add(asset)
    await db.flush()

    return UploadResponse(
        asset_id=asset_id,
        presigned_put_url=presigned_url,
        s3_key=s3_key,
    )

# ═══════════════════════════════════════════════════════════════
# POST /api/v1/images/upload-direct  (proxy upload for local dev)
# ═══════════════════════════════════════════════════════════════

@router.post("/upload-direct", status_code=201)
async def upload_direct(
    file: UploadFile = File(...),
    workspace: WorkspaceContext = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    Proxy upload — browser sends file to FastAPI, which forwards to MinIO.
    Avoids CORS issues with direct browser-to-MinIO uploads in local dev.
    """
    asset_id = uuid4()
    s3_key = f"raw-uploads/{workspace.id}/{asset_id}/{file.filename}"

    file_bytes = await file.read()

    s3_client.put_object(
        Bucket=settings.s3_raw_bucket,
        Key=s3_key,
        Body=file_bytes,
        ContentType=file.content_type or "application/octet-stream",
    )

    asset = ImageAsset(
        id=asset_id,
        workspace_id=workspace.id,
        uploaded_by=workspace.user_id,
        raw_s3_key=s3_key,
        raw_file_size_bytes=len(file_bytes),
        status=ImageStatus.UPLOADED,
    )
    db.add(asset)
    await db.flush()

    return {
        "asset_id": str(asset_id),
        "s3_key": s3_key,
    }


# ═══════════════════════════════════════════════════════════════
# POST /api/v1/images/process
# ═══════════════════════════════════════════════════════════════

@router.post("/process", response_model=ProcessResponse, status_code=202)
async def process_image(
    payload: ProcessRequest,
    workspace: WorkspaceContext = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an uploaded image for AI processing.

    Validates credits, writes a QUEUED status, fires an Inngest event,
    and returns 202 Accepted immediately. The GPU pipeline runs
    asynchronously via Inngest durable functions.
    """
    # Fetch asset scoped to workspace
    result = await db.execute(
        select(ImageAsset).where(
            ImageAsset.id == payload.asset_id,
            ImageAsset.workspace_id == workspace.id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.status != ImageStatus.UPLOADED:
        raise HTTPException(
            status_code=409,
            detail=f"Asset is in '{asset.status.value}' state, cannot reprocess",
        )

    # Calculate credit cost
    credits_required, multiplier = calculate_credit_cost(
        resolution_tier=payload.output_resolution_tier,
        background_preset=payload.background_preset,
        aspect_ratio_count=len(payload.output_aspect_ratios),
    )

    # Check balance
    balance = await check_balance(db, workspace.id)
    if balance < credits_required:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "required": credits_required,
                "available": balance,
            },
        )

    # Debit credits (within transaction)
    await debit_credits(
        db, workspace.id, asset.id, credits_required, multiplier,
    )

    # Update asset status to QUEUED
    asset.status = ImageStatus.QUEUED
    asset.credits_charged = credits_required
    asset.background_preset = payload.background_preset
    asset.output_resolution = payload.output_resolution_tier
    asset.output_aspect_ratio = payload.output_aspect_ratios[0] if payload.output_aspect_ratios else "1:1"

    # Fire Inngest event (if this fails, the transaction rolls back the debit)
    await inngest_client.send(
        inngest.Event(
            name="image/process.requested",
            data={
                "asset_id": str(asset.id),
                "workspace_id": str(workspace.id),
                "background_preset": payload.background_preset,
                "output_aspect_ratios": payload.output_aspect_ratios,
                "output_resolution_tier": payload.output_resolution_tier,
                "webhook_callback_url": payload.webhook_callback_url,
            },
        )
    )

    await db.flush()

    return ProcessResponse(
        job_id=asset.id,
        status="QUEUED",
        credits_charged=credits_required,
        estimated_completion_seconds=45,
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/v1/images/status/{job_id}
# ═══════════════════════════════════════════════════════════════

STAGE_ORDER = ["ANALYZING", "GENERATING_BG"]
STAGE_WEIGHT = {"ANALYZING": 40, "GENERATING_BG": 60}

STAGE_TO_S3_FIELD = {
    "ANALYZING": None,
    "GENERATING_BG": "final_s3_key",
}


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(
    job_id: UUID,
    workspace: WorkspaceContext = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current pipeline status for a job.

    Pure read from Postgres — no GPU coupling whatsoever.
    Returns stage-by-stage progress with percentage.
    """
    result = await db.execute(
        select(ImageAsset).where(
            ImageAsset.id == job_id,
            ImageAsset.workspace_id == workspace.id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Job not found")

    status_value = asset.status.value if isinstance(asset.status, ImageStatus) else asset.status

    # Calculate progress percentage based on pipeline stage
    if status_value in STAGE_ORDER:
        current_idx = STAGE_ORDER.index(status_value)
    elif status_value == "COMPLETED":
        current_idx = len(STAGE_ORDER)
    else:
        current_idx = -1

    if status_value == "COMPLETED":
        progress_pct = 100
    elif current_idx >= 0:
        weights = list(STAGE_WEIGHT.values())
        progress_pct = sum(weights[i] for i in range(current_idx))
    else:
        progress_pct = 0

    # Build stage progress list
    stages = []
    for stage in STAGE_ORDER:
        stage_idx = STAGE_ORDER.index(stage)
        s3_field = STAGE_TO_S3_FIELD.get(stage)
        s3_url = getattr(asset, s3_field, None) if s3_field else None
        stages.append(
            StageProgress(
                stage=stage,
                completed=stage_idx < current_idx,
                s3_url=s3_url,
            )
        )

    return StatusResponse(
        job_id=asset.id,
        status=status_value,
        progress_pct=progress_pct,
        stages=stages,
        final_cdn_url=asset.cdn_url,
        variants=asset.variants_json,
        failure_reason=asset.failure_reason,
        failed_step=asset.failed_step,
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/v1/images — list all assets for workspace
# ═══════════════════════════════════════════════════════════════

@router.get("/")
async def list_images(
    workspace: WorkspaceContext = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """List all image assets for the current workspace."""
    result = await db.execute(
        select(ImageAsset)
        .where(ImageAsset.workspace_id == workspace.id)
        .order_by(ImageAsset.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    assets = result.scalars().all()

    return {
        "items": [
            {
                "id": str(a.id),
                "status": a.status.value if isinstance(a.status, ImageStatus) else a.status,
                "raw_s3_key": a.raw_s3_key,
                "background_preset": a.background_preset,
                "cdn_url": a.cdn_url,
                "credits_charged": a.credits_charged,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in assets
        ],
        "total": len(assets),
        "limit": limit,
        "offset": offset,
    }
