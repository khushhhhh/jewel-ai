"""Credit models — balance cache + append-only audit ledger."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, BigInteger, Numeric,
    DateTime, ForeignKey, CheckConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CreditBalance(Base):
    """
    Denormalized read-optimized credit balance.
    Updated transactionally alongside each ledger insert.
    SUM(delta) reconciliation job runs nightly to catch drift.
    """
    __tablename__ = "credit_balances"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_refilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="credit_balance")

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_credit_balance_non_negative"),
    )


class CreditLedger(Base):
    """
    Append-only audit ledger — never UPDATE/DELETE, only INSERT.
    This is the audit-safe source of truth for all credit movements.
    """
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_assets.id"), nullable=True
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    compute_weight_multiplier: Mapped[float | None] = mapped_column(
        Numeric(4, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_ledger_workspace", "workspace_id", "created_at"),
        CheckConstraint(
            "reason IN ('monthly_grant', 'generation_charge', "
            "'generation_refund', 'manual_adjustment', 'purchase')",
            name="ck_ledger_reason",
        ),
    )
