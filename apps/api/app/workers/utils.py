import io
from app.services.s3_service import s3_client

def download_image_bytes(bucket: str, key: str) -> bytes:
    """Download an object from MinIO and return raw bytes."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()

def upload_image_bytes(bucket: str, key: str, data: bytes, content_type: str = "image/png"):
    """Upload raw bytes to MinIO."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
