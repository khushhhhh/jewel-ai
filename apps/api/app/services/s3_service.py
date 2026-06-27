"""
S3 Service — presigned URL generation for direct browser uploads.

Works with both AWS S3 and MinIO (S3-compatible) for local dev.
"""

import boto3
from botocore.config import Config

from app.config import settings


def _get_s3_client():
    """Create an S3 client configured for the current environment."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


s3_client = _get_s3_client()


def generate_presigned_put_url(
    s3_key: str,
    content_type: str,
    bucket: str | None = None,
    expires_in: int = 900,
) -> str:
    """
    Generate a presigned PUT URL for direct browser upload to S3.

    The browser uploads raw bytes directly to S3, bypassing the API tier
    entirely — no file bytes ever touch the FastAPI process.
    """
    bucket = bucket or settings.s3_raw_bucket
    return s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def generate_presigned_get_url(
    s3_key: str,
    bucket: str | None = None,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned GET URL for serving intermediate artifacts."""
    bucket = bucket or settings.s3_processed_bucket
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
        },
        ExpiresIn=expires_in,
    )
