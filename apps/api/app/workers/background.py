import asyncio
import io
import logging
import os
import urllib.parse
import httpx
from PIL import Image
from huggingface_hub import AsyncInferenceClient

from app.config import settings
from app.workers.utils import download_image_bytes, upload_image_bytes

logger = logging.getLogger("uvicorn")

BACKGROUND_PROMPTS = {
    "pure_white_ecommerce": (
        "pure white seamless infinity cove, shadowless, Shopify product image, "
        "flat diffused light, no objects, 8K, photorealistic"
    ),
    "marble_luxury": (
        "seamless Carrara marble, fine grey veins, soft overhead studio lighting, "
        "luxury jewellery photography, 8K, photorealistic, empty surface"
    ),
    "velvet_dark": (
        "seamless deep navy blue velvet fabric, fine texture, moody studio lighting, "
        "dramatic spotlight, luxury jewellery photography, 8K, photorealistic"
    ),
    "outdoor_editorial": (
        "defocused sunny outdoor garden, beautiful bokeh, golden hour sunlight, "
        "shallow depth of field, fashion editorial jewellery background, 8K, photorealistic"
    ),
    "black_minimal": (
        "pure black seamless background, ultra minimalist, dramatic directional lighting, "
        "luxury e-commerce jewellery photography, 8K, photorealistic"
    ),
    "rose_gold_texture": (
        "brushed rose gold metallic surface, soft reflection, warm studio lighting, "
        "premium luxury aesthetic, empty surface, 8K, photorealistic"
    ),
}

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"

async def fetch_background(preset: str) -> bytes:
    """
    Fetch background using FLUX.1-schnell via Hugging Face API.
    Falls back to Pollinations.ai if HF_TOKEN is missing or API fails.
    """
    prompt_text = BACKGROUND_PROMPTS.get(preset, BACKGROUND_PROMPTS["pure_white_ecommerce"])
    
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        try:
            logger.info(f"[BG-GEN] Fetching background from Hugging Face FLUX.1-schnell")
            client = AsyncInferenceClient("black-forest-labs/FLUX.1-schnell", token=hf_token)
            # HF text_to_image returns a PIL Image
            image = await client.text_to_image(prompt_text, width=1024, height=1024)
            buf = io.BytesIO()
            image.save(buf, format="JPEG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"[BG-GEN] Hugging Face API failed: {e}. Falling back to Pollinations.ai")
    else:
        logger.info("[BG-GEN] HF_TOKEN not found. Using Pollinations.ai as fallback.")

    # Fallback: Pollinations.ai
    encoded_prompt = urllib.parse.quote(prompt_text)
    url = POLLINATIONS_BASE.format(prompt=encoded_prompt)
    logger.info(f"[BG-GEN] Fetching background from Pollinations.ai: {url}")
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            if attempt == 2:
                raise e
            logger.warning(f"[BG-GEN] Attempt {attempt + 1} failed: {e}. Retrying...")
            await asyncio.sleep(2.0)

async def run_background_generation(
    asset_id: str,
    workspace_id: str,
    upscaled_result: dict,
    background_preset: str,
    output_aspect_ratios: list[str],
) -> dict:
    """
    Execute background generation step.
    Fetches AI background and composites transparent product over it.
    """
    prompt = BACKGROUND_PROMPTS.get(background_preset, BACKGROUND_PROMPTS["pure_white_ecommerce"])
    logger.info(
        f"[BG-GEN] Starting background generation for asset {asset_id} "
        f"preset={background_preset}, ratios={output_aspect_ratios}"
    )

    upscaled_s3_key = upscaled_result.get("upscaled_s3_key")
    if not upscaled_s3_key:
        raise ValueError("upscaled_s3_key not found in upscaled_result")

    # 1. Download upscaled transparent product PNG
    upscaled_bytes = download_image_bytes(settings.s3_processed_bucket, upscaled_s3_key)
    product_img = Image.open(io.BytesIO(upscaled_bytes)).convert("RGBA")

    # 2. Fetch background image
    bg_bytes = await fetch_background(background_preset)
    bg_img = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    bg_img = bg_img.resize((1024, 1024), Image.Resampling.LANCZOS)

    variants = []
    for ratio in output_aspect_ratios:
        ratio_slug = ratio.replace(":", "x")
        
        # 3. Composite: Paste product onto background using product's alpha channel as mask
        composite = bg_img.copy()
        composite.paste(product_img, (0, 0), mask=product_img)

        # 4. Convert final composite to RGB and save as JPEG
        final_rgb = composite.convert("RGB")
        buf = io.BytesIO()
        final_rgb.save(buf, format="JPEG", quality=92)
        final_bytes = buf.getvalue()

        # 5. Upload final JPEG to processed bucket
        final_key = f"processed/{asset_id}/final/final_{ratio_slug}.jpg"
        upload_image_bytes(settings.s3_processed_bucket, final_key, final_bytes, "image/jpeg")

        variants.append({
            "aspect_ratio": ratio,
            "s3_key": final_key,
            "cdn_url": f"{settings.s3_endpoint_url}/{settings.s3_processed_bucket}/{final_key}",
        })

    # Primary output is the first variant
    primary = variants[0] if variants else {}

    logger.info(f"[BG-GEN] Completed background generation for asset {asset_id}")

    return {
        "final_s3_key": primary.get("s3_key"),
        "cdn_url": primary.get("cdn_url"),
        "variants": variants,
        "background_preset": background_preset,
        "prompt_used": prompt,
    }
