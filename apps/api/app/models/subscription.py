"""SubscriptionTier model — plan definitions and limits."""

from sqlalchemy import String, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SubscriptionTier(Base):
    __tablename__ = "subscription_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    monthly_credit_grant: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_resolution: Mapped[str] = mapped_column(String(20), nullable=False)
    price_cents_monthly: Mapped[int] = mapped_column(Integer, nullable=False)
    concurrent_jobs_limit: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
