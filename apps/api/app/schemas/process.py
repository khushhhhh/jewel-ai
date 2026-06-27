"""Process endpoint request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    asset_id: UUID
    background_preset: str = Field(
        ...,
        pattern=r"^(pure_white_ecommerce|marble_luxury|velvet_dark|outdoor_editorial|auto)$",
    )
    output_aspect_ratios: list[str] = Field(default=["1:1"], max_length=4)
    output_resolution_tier: str = Field(
        default="standard",
        pattern=r"^(standard|hd|4k)$",
    )
    webhook_callback_url: str | None = None  # Enterprise tier only


class ProcessResponse(BaseModel):
    job_id: UUID
    status: str
    credits_charged: int
    estimated_completion_seconds: int
