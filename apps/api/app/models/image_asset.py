"""ImageAsset model — core pipeline state machine."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, BigInteger, SmallInteger, Text,
    DateTime, ForeignKey, Index, Enum, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImageStatus(str, enum.Enum):
    """Pipeline state machine states."""
    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    QUEUED = "QUEUED"
    MASKING = "MASKING"
    MASKED = "MASKED"
    CLEANING = "CLEANING"
    UPSCALING = "UPSCALING"
    GENERATING_BG = "GENERATING_BG"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImageAsset(Base):
    __tablename__ = "image_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Raw file metadata
    raw_s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Pipeline state
    status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, name="image_status", create_constraint=True),
        nullable=False,
        default=ImageStatus.UPLOADED,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Per-stage artifact pointers (nullable until stage completes)
    mask_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cleaned_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    upscaled_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    final_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cdn_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Processing config
    background_preset: Mapped[str | None] = mapped_column(String(50), nullable=True)
    output_aspect_ratio: Mapped[str | None] = mapped_column(String(10), nullable=True)
    output_resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    variants_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Orchestration
    inngest_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credits_charged: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="image_assets")
    uploader = relationship("User")

    __table_args__ = (
        Index("idx_assets_workspace_status", "workspace_id", "status"),
        Index("idx_assets_inngest_run", "inngest_run_id"),
    )
