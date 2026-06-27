import base64
import json
import logging
import os
from anthropic import AsyncAnthropic

from app.config import settings
from app.workers.utils import download_image_bytes

logger = logging.getLogger("uvicorn")

SYSTEM_PROMPT = """You are an expert luxury jewelry art director.
Analyze the provided product image and return a JSON object with the following structure:
{
    "product_type": "string (e.g. ring, necklace, earring, watch, bracelet)",
    "material": "string (e.g. white gold, yellow gold, silver, rose gold, ruby, emerald, none)",
    "visual_tone": "string (e.g. costume, mid-tier, luxury, vintage, minimalist, ornate)",
    "lighting": "string (warm, cool, or neutral - based on how the product was shot)",
    "prompts": {
        "ecommerce_clean": "A natural language editing instruction for Gemini to place the product on a clean, white or near-white ecommerce background. Emphasize studio lighting and a clean infinity cove. Crucial: ALWAYS include 'Preserve the jewellery exactly. Do not modify the product itself.'",
        "lifestyle_editorial": "A natural language editing instruction for Gemini to place the product in a beautiful lifestyle or environmental scene tailored to this specific item. If it's a luxury diamond ring, maybe a romantic or opulent setting. Crucial: ALWAYS include 'Preserve the jewellery exactly. Do not modify the product itself.'",
        "moody_luxury": "A natural language editing instruction for Gemini to place the product in a dark, dramatic, high-contrast moody luxury background suitable for Instagram or boutique listings. Crucial: ALWAYS include 'Preserve the jewellery exactly. Do not modify the product itself.'"
    }
}
Return ONLY the raw JSON object, no markdown blocks, no other text.
"""

async def run_analyzer(
    asset_id: str,
    workspace_id: str,
    raw_s3_key: str,
) -> dict:
    """
    Stage 0: Art Director (Claude Vision).
    Analyzes the raw uploaded image to extract product details and generate bespoke prompts.
    """
    logger.info(f"[ANALYZER] Starting Claude Vision analysis for asset {asset_id}")

    # 1. Download raw image bytes
    image_bytes = download_image_bytes(settings.s3_raw_bucket, raw_s3_key)
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("[ANALYZER] ANTHROPIC_API_KEY not found. Returning fallback analysis.")
        return _fallback_analysis()

    client = AsyncAnthropic(api_key=api_key)

    try:
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg", # Anthropics API generally accepts jpeg/png
                                "data": base64_image,
                            }
                        },
                        {
                            "type": "text",
                            "text": "Analyze this jewelry item and provide the JSON."
                        }
                    ]
                }
            ]
        )
        
        content = response.content[0].text.strip()
        # Clean up any potential markdown formatting
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
            
        analysis_json = json.loads(content)
        logger.info(f"[ANALYZER] Successfully generated analysis: {analysis_json.get('product_type')}")
        return {"analysis_json": analysis_json}

    except Exception as e:
        logger.error(f"[ANALYZER] Claude API failed: {e}")
        return _fallback_analysis()

def _fallback_analysis() -> dict:
    return {
        "analysis_json": {
            "product_type": "jewelry",
            "material": "mixed",
            "visual_tone": "standard",
            "lighting": "neutral",
            "prompts": {
                "ecommerce_clean": "Using this product photograph, place it in a pure white seamless infinity cove. Shadowless, flat diffused light, photorealistic. Preserve the jewellery exactly. Do not modify the product itself.",
                "lifestyle_editorial": "Using this product photograph, place it in a defocused sunny outdoor garden with beautiful bokeh and golden hour sunlight. Fashion editorial background, 8K. Preserve the jewellery exactly. Do not modify the product itself.",
                "moody_luxury": "Using this product photograph, place it on a pure black seamless background with ultra minimalist, dramatic directional lighting. Luxury e-commerce jewellery photography, 8K. Preserve the jewellery exactly. Do not modify the product itself."
            }
        }
    }
