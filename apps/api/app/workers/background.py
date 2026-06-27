import asyncio
import io
import logging
import os
import uuid
from typing import Dict, Any

from google import genai
from google.genai import types

from app.config import settings
from app.workers.utils import download_image_bytes, upload_image_bytes

logger = logging.getLogger("uvicorn")


async def run_background_generation(
    asset_id: str,
    workspace_id: str,
    raw_s3_key: str,
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stage 1: Native Multimodal Image Editing using Gemini.
    Generates 3 variants by providing the raw image and 3 bespoke prompts directly to Gemini.
    """
    logger.info(f"[GEMINI] Starting image generation for asset {asset_id}")

    # 1. Download raw image
    raw_bytes = download_image_bytes(settings.s3_raw_bucket, raw_s3_key)

    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.warning("GEMINI_API_KEY not found. Using fallback mock generation.")
        return await _mock_background_generation(asset_id, workspace_id, analysis_result)

    client = genai.Client(api_key=gemini_api_key)

    prompts = analysis_result.get("analysis_json", {}).get("prompts", {})
    if not prompts:
        raise ValueError("No prompts found in analysis_json")

    variants = []

    # 2. Iterate through prompts and generate variants
    for variant_name, prompt_text in prompts.items():
        logger.info(f"[GEMINI] Generating variant: {variant_name}")
        
        try:
            # We use gemini-2.5-flash as the architecture instructs
            # Depending on Google GenAI SDK specifics for image output, we provide the part and request image response.
            response = await client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(data=raw_bytes, mime_type='image/jpeg'),
                    prompt_text,
                ],
                config=types.GenerateContentConfig(
                    # Inform the model we expect an image response if supported natively,
                    # or it may be configured as a tool/output constraint.
                    response_mime_type="image/jpeg",
                )
            )

            # Extract the raw image bytes from the response
            # Assuming the multimodal API returns inline_data for images
            output_bytes = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        output_bytes = part.inline_data.data
                        break
            
            if not output_bytes:
                raise ValueError("No image data returned from Gemini API")

            # 3. Upload variant to MinIO
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
            logger.info(f"[GEMINI] Variant {variant_name} generated and saved to {cdn_url}")
            
        except Exception as e:
            logger.error(f"[GEMINI] Failed to generate {variant_name}: {e}")
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
    """Mock implementation when GEMINI_API_KEY is missing."""
    from PIL import Image
    
    prompts = analysis_result.get("analysis_json", {}).get("prompts", {})
    variants = []
    
    for variant_name, prompt_text in prompts.items():
        # Create a dummy image
        img = Image.new('RGB', (1024, 1024), color=(73, 109, 137))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
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
