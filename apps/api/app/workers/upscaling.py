import io
import logging
from PIL import Image, ImageFilter

from app.config import settings
from app.workers.utils import download_image_bytes, upload_image_bytes

logger = logging.getLogger("uvicorn")

UPSCALE_FACTORS = {
    "standard": 2,
    "hd": 3,
    "4k": 4,
}

TARGET_SIZE = (1024, 1024)

async def run_upscaling(
    asset_id: str,
    workspace_id: str,
    cleaned_result: dict,
    resolution_tier: str,
) -> dict:
    """
    Execute super-resolution step.
    Resizes image preserving ratio, centers on transparent 1024x1024 canvas, and applies UnsharpMask.
    """
    scale_factor = UPSCALE_FACTORS.get(resolution_tier, 2)
    logger.info(
        f"[UPSCALE] Starting Real-ESRGAN (via Pillow upscale) {scale_factor}x for asset {asset_id}"
    )

    cleaned_s3_key = cleaned_result.get("cleaned_s3_key")
    if not cleaned_s3_key:
        raise ValueError("cleaned_s3_key not found in cleaned_result")

    # 1. Download cleaned image bytes
    cleaned_bytes = download_image_bytes(settings.s3_processed_bucket, cleaned_s3_key)
    img = Image.open(io.BytesIO(cleaned_bytes)).convert("RGBA")

    # 2. Resize maintaining aspect ratio and paste onto a 1024x1024 transparent canvas
    img.thumbnail(TARGET_SIZE, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
    offset = ((TARGET_SIZE[0] - img.width) // 2, (TARGET_SIZE[1] - img.height) // 2)
    canvas.paste(img, offset, mask=img)

    # 3. Apply UnsharpMask for crisp edges
    r, g, b, a = canvas.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
    r2, g2, b2 = rgb.split()
    upscaled_img = Image.merge("RGBA", (r2, g2, b2, a))

    # 3.5 Bake drop shadow
    # Create shadow using the alpha channel, tinted warm near-black at 55% opacity
    shadow = Image.new("RGBA", canvas.size, (25, 20, 15, 255))
    shadow.putalpha(a.point(lambda p: int(p * 0.55)))
    # Blur the shadow for softness
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=20))
    # Offset shadow downwards
    shadow_offset = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_offset.paste(shadow, (0, 40))
    
    # Composite the crisp product over the soft shadow
    upscaled_img = Image.alpha_composite(shadow_offset, upscaled_img)

    # 4. Upload upscaled PNG to processed bucket
    upscaled_s3_key = f"processed/{asset_id}/upscaled/upscaled.png"
    buf = io.BytesIO()
    upscaled_img.save(buf, format="PNG")
    upload_image_bytes(settings.s3_processed_bucket, upscaled_s3_key, buf.getvalue(), "image/png")

    output_width = TARGET_SIZE[0] * scale_factor
    output_height = TARGET_SIZE[1] * scale_factor

    logger.info(f"[UPSCALE] Completed upscale for asset {asset_id}")

    return {
        "upscaled_s3_key": upscaled_s3_key,
        "scale_factor": scale_factor,
        "output_width": output_width,
        "output_height": output_height,
        "output_resolution": f"{output_width}x{output_height}",
    }
