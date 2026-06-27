"""
Seed script — populates subscription tiers and a demo workspace for development.

Run with: python -m app.seed
"""

import asyncio
from uuid import uuid4

from app.database import async_session_factory, init_db
from app.models.workspace import Workspace
from app.models.user import User
from app.models.subscription import SubscriptionTier
from app.models.credit import CreditBalance, CreditLedger


SUBSCRIPTION_TIERS = [
    {
        "name": "free",
        "monthly_credit_grant": 10,
        "max_output_resolution": "1024x1024",
        "price_cents_monthly": 0,
        "concurrent_jobs_limit": 1,
    },
    {
        "name": "starter",
        "monthly_credit_grant": 100,
        "max_output_resolution": "2048x2048",
        "price_cents_monthly": 2900,
        "concurrent_jobs_limit": 3,
    },
    {
        "name": "pro",
        "monthly_credit_grant": 500,
        "max_output_resolution": "4096x4096",
        "price_cents_monthly": 9900,
        "concurrent_jobs_limit": 5,
    },
    {
        "name": "enterprise",
        "monthly_credit_grant": 5000,
        "max_output_resolution": "4096x4096",
        "price_cents_monthly": 49900,
        "concurrent_jobs_limit": 20,
    },
]


async def seed():
    await init_db()

    async with async_session_factory() as db:
        # Seed subscription tiers
        for tier_data in SUBSCRIPTION_TIERS:
            tier = SubscriptionTier(**tier_data)
            db.add(tier)

        # Create demo workspace
        workspace_id = uuid4()
        user_id = uuid4()

        workspace = Workspace(
            id=workspace_id,
            name="Demo Jewelry Studio",
            slug="demo-studio",
            plan_tier="pro",
        )
        db.add(workspace)
        await db.flush()

        user = User(
            id=user_id,
            workspace_id=workspace_id,
            email="demo@jewel-ai.dev",
            role="owner",
        )
        db.add(user)

        credit_balance = CreditBalance(
            workspace_id=workspace_id,
            balance=500,
        )
        db.add(credit_balance)

        # Initial credit grant ledger entry
        ledger = CreditLedger(
            workspace_id=workspace_id,
            delta=500,
            reason="monthly_grant",
        )
        db.add(ledger)

        await db.commit()

        print(f"✅ Seeded subscription tiers: {[t['name'] for t in SUBSCRIPTION_TIERS]}")
        print(f"✅ Created demo workspace: {workspace.name} ({workspace.slug})")
        print(f"   Workspace ID: {workspace_id}")
        print(f"   User ID:      {user_id}")
        print(f"   Email:        demo@jewel-ai.dev")
        print(f"   Credits:      500")
        print()
        print("Use these headers for API requests:")
        print(f"   X-Workspace-Id: {workspace_id}")
        print(f"   X-User-Id: {user_id}")


if __name__ == "__main__":
    asyncio.run(seed())
