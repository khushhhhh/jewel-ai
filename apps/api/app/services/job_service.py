"""
Job Service — image asset lifecycle management.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image_asset import ImageAsset, ImageStatus


async def get_asset(
    db: AsyncSession,
    asset_id: UUID,
    workspace_id: UUID,
) -> ImageAsset | None:
    """Fetch an image asset scoped to a workspace."""
    result = await db.execute(
        select(ImageAsset).where(
            ImageAsset.id == asset_id,
            ImageAsset.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def update_status(
    db: AsyncSession,
    asset_id: UUID,
    status: ImageStatus,
    **extra_fields,
) -> None:
    """Update an asset's pipeline status with optional extra fields."""
    values = {"status": status, **extra_fields}
    if status == ImageStatus.COMPLETED:
        values["completed_at"] = datetime.now(timezone.utc)
    await db.execute(
        update(ImageAsset).where(ImageAsset.id == asset_id).values(**values)
    )
    await db.commit()


async def mark_failed(
    db: AsyncSession,
    asset_id: UUID,
    failed_step: str,
    failure_reason: str,
) -> None:
    """Mark a job as failed with the step that caused the failure."""
    await db.execute(
        update(ImageAsset)
        .where(ImageAsset.id == asset_id)
        .values(
            status=ImageStatus.FAILED,
            failed_step=failed_step,
            failure_reason=failure_reason,
        )
    )
    await db.commit()
