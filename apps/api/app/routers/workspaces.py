"""
Workspace API Router — CRUD and management.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.workspace import Workspace
from app.models.user import User
from app.models.credit import CreditBalance

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=100, pattern=r"^[a-z0-9-]+$")
    owner_email: str = Field(..., max_length=255)


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan_tier: str
    credit_balance: int
    user_id: str | None = None


@router.post("/", status_code=201)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace with owner user and initial credits."""
    # Check slug uniqueness
    existing = await db.execute(
        select(Workspace).where(Workspace.slug == payload.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Workspace slug already taken")

    workspace_id = uuid4()
    user_id = uuid4()

    # Create workspace
    workspace = Workspace(
        id=workspace_id,
        name=payload.name,
        slug=payload.slug,
    )
    db.add(workspace)

    # Create owner user
    user = User(
        id=user_id,
        workspace_id=workspace_id,
        email=payload.owner_email,
        role="owner",
    )
    db.add(user)

    # Initialize credit balance (free tier: 10 credits)
    credit_balance = CreditBalance(
        workspace_id=workspace_id,
        balance=10,
    )
    db.add(credit_balance)

    await db.flush()

    return {
        "workspace_id": str(workspace_id),
        "user_id": str(user_id),
        "name": payload.name,
        "slug": payload.slug,
        "plan_tier": "free",
        "credit_balance": 10,
    }


@router.get("/{slug}")
async def get_workspace(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get workspace details by slug."""
    result = await db.execute(
        select(Workspace).where(Workspace.slug == slug)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Get credit balance
    balance_result = await db.execute(
        select(CreditBalance).where(
            CreditBalance.workspace_id == workspace.id
        )
    )
    credit_balance = balance_result.scalar_one_or_none()

    # Get user
    user_result = await db.execute(
        select(User).where(User.workspace_id == workspace.id)
    )
    user = user_result.scalars().first()

    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "slug": workspace.slug,
        "plan_tier": workspace.plan_tier,
        "credit_balance": credit_balance.balance if credit_balance else 0,
        "user_id": str(user.id) if user else None,
    }
