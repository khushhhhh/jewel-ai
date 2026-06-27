"""
background.py — Gemini Native Multimodal Image Editing

Uses gemini-2.0-flash-preview-image-generation which natively understands
the input image's lighting, physics, and context and re-renders the entire
scene with the product still in it. No cutting, no compositing.

Claude (analyzer.py) writes 3 bespoke editing prompts for this specific
product. We fire 3 calls in sequence, get back 3 coherent product photos.
"""
import io
import logging
import os
import uuid
from typing import Dict, Any

from PIL import Image
from google import genai
from google.genai import types

from app.config import settings
from app.workers.utils import download_image_bytes, upload_image_bytes

logger = logging.getLogger("uvicorn")

# The only Gemini model that supports image output in the SDK today
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"


async def run_background_generation(
    asset_id: str,
    workspace_id: str,
    raw_s3_key: str,
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stage 1: Native Multimodal Image Editing using Gemini.

    Sends the raw product photo + Claude's bespoke scene prompt directly to
    Gemini. The model sees the ring's existing metal, reflections, and light
    and physically re-renders it inside the requested scene — no compositing.

    3 variants generated per call: Ecommerce Clean, Lifestyle Editorial,
    Moody Luxury.
    """
    logger.info(f"[GEMINI] Starting image generation for asset {asset_id}")

    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.warning("[GEMINI] GEMINI_API_KEY not set. Returning mock images.")
        return await _mock_background_generation(asset_id, workspace_id, analysis_result)

    # 1. Download raw image bytes and wrap as PIL (Gemini SDK accepts PIL directly)
    raw_bytes = download_image_bytes(settings.s3_raw_bucket, raw_s3_key)
    pil_image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")

    client = genai.Client(api_key=gemini_api_key)

    prompts: Dict[str, str] = analysis_result.get("analysis_json", {}).get("prompts", {})
    if not prompts:
        logger.error("[GEMINI] No prompts in analysis_json — using fallback prompts")
        prompts = {
            "ecommerce_clean": (
                "Place this jewellery on a pure white seamless infinity cove. "
                "Shadowless, flat diffused studio light, photorealistic product photography. "
                "Preserve the jewellery exactly. Do not modify the product itself."
            ),
            "lifestyle_editorial": (
                "Place this jewellery on draped grey silk fabric next to a navy velvet "
                "jewellery box. Warm ambient light, shallow depth of field, commercial photography. "
                "Preserve the jewellery exactly. Do not modify the product itself."
            ),
            "moody_luxury": (
                "Place this jewellery on a pure black seamless background. "
                "Single dramatic directional spotlight, ultra minimalist, luxury editorial. "
                "Preserve the jewellery exactly. Do not modify the product itself."
            ),
        }

    variants = []

    for variant_name, prompt_text in prompts.items():
        logger.info(f"[GEMINI] Generating variant: {variant_name}")

        try:
            # KEY: response_modalities must include IMAGE to get pixel output back.
            # The model sees the full input photo, understands the product's light
            # and material, then re-renders the WHOLE scene coherently.
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=[prompt_text, pil_image],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                ),
            )

            # Extract image bytes from response
            output_bytes = None
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    output_bytes = part.inline_data.data
                    break

            if not output_bytes:
                raise ValueError(f"No image bytes returned from Gemini for variant {variant_name}")

            # 3. Save to MinIO
            s3_key = f"{workspace_id}/{asset_id}_{variant_name}_{uuid.uuid4().hex[:8]}.jpg"
            cdn_url = upload_image_bytes(
                bucket=settings.s3_processed_bucket,
                key=s3_key,
                data=output_bytes,
                content_type="image/jpeg",
            )

            variants.append({
                "variant_name": variant_name,
                "prompt_used": prompt_text,
                "s3_key": s3_key,
                "cdn_url": cdn_url,
            })
            logger.info(f"[GEMINI] ✓ Variant '{variant_name}' saved → {cdn_url}")

        except Exception as e:
            logger.error(f"[GEMINI] ✗ Variant '{variant_name}' failed: {e}")
            raise e

    return {
        "variants": variants,
        "final_s3_key": variants[0]["s3_key"] if variants else None,
        "cdn_url": variants[0]["cdn_url"] if variants else None,
    }


async def _mock_background_generation(
    asset_id: str,
    workspace_id: str,
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Fallback used when GEMINI_API_KEY is absent.
    Generates solid-colour placeholder images so the rest of the
    pipeline still completes and the UI can be tested end-to-end.
    Set GEMINI_API_KEY in your .env to switch to real generation.
    """
    prompts: Dict[str, str] = (
        analysis_result.get("analysis_json", {}).get("prompts", {})
        or {
            "ecommerce_clean": "mock",
            "lifestyle_editorial": "mock",
            "moody_luxury": "mock",
        }
    )

    # Each mock variant gets a distinct colour so you can tell them apart
    mock_colours = {
        "ecommerce_clean": (240, 240, 240),   # light grey — clean bg
        "lifestyle_editorial": (180, 140, 90), # warm golden
        "moody_luxury": (20, 20, 30),          # near-black
    }
    variants = []

    for variant_name, prompt_text in prompts.items():
        colour = mock_colours.get(variant_name, (128, 128, 128))
        img = Image.new("RGB", (1024, 1024), color=colour)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        output_bytes = buf.getvalue()

        s3_key = f"{workspace_id}/{asset_id}_{variant_name}_{uuid.uuid4().hex[:8]}.jpg"
        cdn_url = upload_image_bytes(
            bucket=settings.s3_processed_bucket,
            key=s3_key,
            data=output_bytes,
            content_type="image/jpeg",
        )
        variants.append({
            "variant_name": variant_name,
            "prompt_used": prompt_text,
            "s3_key": s3_key,
            "cdn_url": cdn_url,
        })

    return {
        "variants": variants,
        "final_s3_key": variants[0]["s3_key"] if variants else None,
        "cdn_url": variants[0]["cdn_url"] if variants else None,
    }
