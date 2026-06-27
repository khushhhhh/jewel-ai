"""
Credit Service — transactional credit debit/refund with audit ledger.

Credit cost is computed at job-submission time as:
    base_cost × resolution_multiplier × background_complexity_multiplier × aspect_ratio_count
"""

from math import ceil
from uuid import UUID

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditBalance, CreditLedger

# Resolution multiplier — higher res = more GPU time = more credits
RESOLUTION_MULTIPLIER = {
    "standard": 1.0,
    "hd": 1.5,
    "4k": 2.5,
}

# Background complexity multiplier — lifestyle scenes are more GPU-intensive
BACKGROUND_MULTIPLIER = {
    "pure_white_ecommerce": 1.0,
    "marble_luxury": 1.3,
    "velvet_dark": 1.3,
    "outdoor_editorial": 1.5,
}


def calculate_credit_cost(
    resolution_tier: str,
    background_preset: str,
    aspect_ratio_count: int,
    base_cost: int = 1,
) -> tuple[int, float]:
    """
    Calculate the credit cost for a job.

    Returns:
        (credits_required, multiplier)
    """
    multiplier = (
        RESOLUTION_MULTIPLIER.get(resolution_tier, 1.0)
        * BACKGROUND_MULTIPLIER.get(background_preset, 1.0)
        * aspect_ratio_count
    )
    return ceil(base_cost * multiplier), multiplier


async def check_balance(
    db: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Get current credit balance for a workspace."""
    result = await db.execute(
        select(CreditBalance.balance).where(
            CreditBalance.workspace_id == workspace_id
        )
    )
    balance = result.scalar_one_or_none()
    return balance if balance is not None else 0


async def debit_credits(
    db: AsyncSession,
    workspace_id: UUID,
    image_asset_id: UUID,
    credits_required: int,
    multiplier: float,
) -> None:
    """
    Debit credits from a workspace's balance and record in the ledger.

    Must be called within an active transaction — if the downstream
    Inngest send() fails, the caller's transaction rolls back this debit.
    """
    # Update cached balance
    await db.execute(
        update(CreditBalance)
        .where(CreditBalance.workspace_id == workspace_id)
        .values(balance=CreditBalance.balance - credits_required)
    )

    # Append to audit ledger
    ledger_entry = CreditLedger(
        workspace_id=workspace_id,
        image_asset_id=image_asset_id,
        delta=-credits_required,
        reason="generation_charge",
        compute_weight_multiplier=multiplier,
    )
    db.add(ledger_entry)


async def refund_credits(
    db: AsyncSession,
    workspace_id: UUID,
    image_asset_id: UUID,
    credits_amount: int,
) -> None:
    """
    Refund credits for a failed job — positive delta in the ledger.

    Called by the Inngest failure handler when a pipeline stage
    fails after max retries.
    """
    await db.execute(
        update(CreditBalance)
        .where(CreditBalance.workspace_id == workspace_id)
        .values(balance=CreditBalance.balance + credits_amount)
    )

    ledger_entry = CreditLedger(
        workspace_id=workspace_id,
        image_asset_id=image_asset_id,
        delta=credits_amount,
        reason="generation_refund",
    )
    db.add(ledger_entry)
