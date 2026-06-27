"""Upload endpoint request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., pattern=r"^image/(jpeg|png|heic|webp)$")
    file_size_bytes: int = Field(..., gt=0, le=50_000_000)  # 50MB hard cap


class UploadResponse(BaseModel):
    asset_id: UUID
    presigned_put_url: str
    s3_key: str
    expires_in: int = 900  # 15 minutes
