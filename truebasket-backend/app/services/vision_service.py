"""Unified Vision Service Interface.

Selects and dispatches multimodal inference to either:
1. OpenRouter Vision (PillSync Base64 approach, default/recommended)
2. Google Developer API (Gemma 4 via google-genai)
3. Hosted OpenAI-compatible endpoint (vLLM / AWS Bedrock proxy)

Ensures zero disruption to the existing API contract and transparent provider interchangeability.
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple

from app.config import get_settings
from app.services.gemma_service import (
    _extract_json,
    inspect_gemma_configuration,
    run_gemma_image_smoke_test,
)
from app.services.openrouter_service import (
    _extract_json_from_response,
    infer_openrouter_vision,
    OpenRouterConfigError,
    OpenRouterError,
)

logger = logging.getLogger("truebasket.services.vision")


def inspect_vision_configuration() -> Tuple[bool, Dict[str, Any]]:
    """Inspect current vision configuration and active provider status."""
    settings = get_settings()
    configured_provider = (settings.ai_vision_provider or "openrouter").lower().strip()

    if configured_provider == "openrouter":
        is_ready = settings.is_openrouter_configured
        details = (
            f"Ready using OpenRouter Vision with model '{settings.openrouter_vision_model}'"
            if is_ready
            else "OPENROUTER_API_KEY is not configured in .env."
        )
        return is_ready, {
            "provider": "openrouter",
            "model": settings.openrouter_vision_model,
            "configured": is_ready,
            "multimodal_supported": True,
            "details": details,
            "setup_guide": (
                "Set OPENROUTER_API_KEY=sk-or-v1-... in your .env file.\n"
                "Optional: OPENROUTER_VISION_MODEL=google/gemma-3-27b-it"
            ),
        }
    else:
        # Fallback to Gemma inspection
        return inspect_gemma_configuration()


async def run_vision_image_inference(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    prompt: str = "",
) -> Dict[str, Any]:
    """Execute multimodal vision inference through the configured vision provider.

    Returns:
        {
            "success": bool,
            "provider": str,
            "model": str,
            "response_text": str,
            "structured_output": Optional[Dict[str, Any]],
            "latency_ms": float,
        }
    """
    settings = get_settings()
    active_provider = settings.active_vision_provider

    start_time = time.perf_counter()

    if active_provider == "openrouter":
        try:
            content, diagnostics = await infer_openrouter_vision(
                image_bytes=image_bytes,
                mime_type=mime_type,
                prompt=prompt,
            )
            structured = _extract_json_from_response(content)
            return {
                "success": True,
                "provider": "openrouter",
                "model": diagnostics["model"],
                "response_text": content,
                "structured_output": structured,
                "latency_ms": diagnostics["latency_ms"],
            }
        except OpenRouterError as o_err:
            logger.warning("[Vision Service] OpenRouter vision failed: %s", o_err)
            # If Google Gemma is configured as secondary fallback, attempt it
            if settings.is_gemma_configured:
                logger.info("[Vision Service] Falling back to configured Gemma provider...")
                gemma_resp = await run_gemma_image_smoke_test(
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    prompt=prompt,
                )
                return {
                    "success": gemma_resp.success,
                    "provider": gemma_resp.provider,
                    "model": gemma_resp.model,
                    "response_text": gemma_resp.response_text,
                    "structured_output": gemma_resp.structured_output,
                    "latency_ms": gemma_resp.latency_ms,
                }
            raise

    # Default to Gemma integration
    gemma_resp = await run_gemma_image_smoke_test(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=prompt,
    )
    return {
        "success": gemma_resp.success,
        "provider": gemma_resp.provider,
        "model": gemma_resp.model,
        "response_text": gemma_resp.response_text,
        "structured_output": gemma_resp.structured_output,
        "latency_ms": gemma_resp.latency_ms,
    }
