"""Status endpoint response schemas."""

from uuid import UUID

from pydantic import BaseModel


class StageProgress(BaseModel):
    stage: str
    completed: bool
    s3_url: str | None = None


class StatusResponse(BaseModel):
    job_id: UUID
    status: str
    progress_pct: int
    stages: list[StageProgress]
    final_cdn_url: str | None = None
    variants: list[dict] | None = None
    failure_reason: str | None = None
    failed_step: str | None = None
