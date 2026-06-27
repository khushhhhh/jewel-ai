"""Workspace model — B2B multi-tenant root entity."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
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

    # Relationships
    users = relationship("User", back_populates="workspace", cascade="all, delete-orphan")
    image_assets = relationship("ImageAsset", back_populates="workspace", cascade="all, delete-orphan")
    credit_balance = relationship("CreditBalance", back_populates="workspace", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "plan_tier IN ('free', 'starter', 'pro', 'enterprise')",
            name="ck_workspaces_plan_tier",
        ),
    )
