"""
Auth middleware — JWT validation and workspace context injection.

For local development, provides a mock workspace/user context.
In production, validates JWT tokens (Clerk, Auth0, or custom).
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.workspace import Workspace
from app.models.user import User


class WorkspaceContext:
    """Injected into route handlers as the current authenticated workspace."""

    def __init__(self, workspace_id: UUID, user_id: UUID, workspace: Workspace):
        self.id = workspace_id
        self.user_id = user_id
        self.workspace = workspace


async def get_current_workspace(
    x_workspace_id: str | None = Header(None),
    x_user_id: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """
    FastAPI dependency — resolves the current workspace context.

    Dev mode: accepts workspace/user IDs via headers (no JWT validation).
    Production: would validate JWT and extract from token claims.
    """
    if not x_workspace_id or not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Workspace-Id or X-User-Id headers",
        )

    try:
        workspace_id = UUID(x_workspace_id)
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace or user ID format")

    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=user_id,
        workspace=workspace,
    )
