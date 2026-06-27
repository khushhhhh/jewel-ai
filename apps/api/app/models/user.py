"""User model — workspace member."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="users")

    __table_args__ = (
        Index("idx_users_workspace", "workspace_id"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_users_role",
        ),
    )
