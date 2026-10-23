"""OpenRouter Vision AI Service (Proven PillSync Approach).

Implements OpenAI-compatible `/api/v1/chat/completions` endpoint with:
- Base64 data URL multimodal inputs
- Bounded retry for transient 429/5xx errors
- Strict secrets sanitization in logging and error messages
- Comprehensive runtime diagnostics
"""

import asyncio
import base64
import io
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image

from app.config import get_settings

logger = logging.getLogger("truebasket.services.openrouter")


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class OpenRouterError(Exception):
    """Base exception for OpenRouter operations."""
    pass


class OpenRouterConfigError(OpenRouterError):
    """Raised when OpenRouter API key or configuration is missing."""
    pass


class OpenRouterAuthError(OpenRouterError):
    """Raised on authentication/authorization failure (HTTP 401, 403). Permanent."""
    pass


class OpenRouterRateLimitError(OpenRouterError):
    """Raised on rate limits or quota exhaustion (HTTP 429). Transient."""
    pass


class OpenRouterServerError(OpenRouterError):
    """Raised on provider server errors (HTTP 500, 502, 503, 504). Transient."""
    pass


class OpenRouterInvalidRequestError(OpenRouterError):
    """Raised on client or parameter error (HTTP 400, 404, 422). Permanent."""
    pass


class OpenRouterTimeoutError(OpenRouterError):
    """Raised when an OpenRouter request times out."""
    pass


class OpenRouterEmptyResponseError(OpenRouterError):
    """Raised when model returns empty content."""
    pass


class OpenRouterInferenceError(OpenRouterError):
    """Raised on general inference or parsing failures."""
    pass


# ==============================================================================
# Helper Functions & Sanitation
# ==============================================================================

def sanitize_error_message(msg: str, api_key: Optional[str] = None) -> str:
    """Sanitize error messages to ensure API keys and Base64 payloads are never exposed."""
    cleaned = str(msg)
    if api_key and len(api_key) > 6:
        cleaned = cleaned.replace(api_key, "[REDACTED_API_KEY]")
    # Redact base64 image strings if present in error outputs
    cleaned = re.sub(r"data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+\/=\-_]{30,}", "[REDACTED_BASE64_IMAGE]", cleaned)
    return cleaned


def _classify_http_error(status_code: int, response_text: str, api_key: Optional[str] = None) -> OpenRouterError:
    """Classify HTTP status codes into specific domain exceptions."""
    sanitized = sanitize_error_message(response_text, api_key)
    # Parse error detail if available in JSON
    detail = sanitized
    try:
        err_json = json.loads(response_text)
        if isinstance(err_json, dict) and "error" in err_json:
            err_obj = err_json["error"]
            if isinstance(err_obj, dict):
                detail = err_obj.get("message") or str(err_obj)
            else:
                detail = str(err_obj)
    except Exception:
        pass

    detail = sanitize_error_message(detail, api_key)

    if status_code in (401, 403):
        return OpenRouterAuthError(f"OpenRouter authentication failed (HTTP {status_code}): {detail}")
    if status_code == 429:
        return OpenRouterRateLimitError(f"OpenRouter rate limit or quota exceeded (HTTP 429): {detail}")
    if status_code in (500, 502, 503, 504):
        return OpenRouterServerError(f"OpenRouter provider server error (HTTP {status_code}): {detail}")
    if status_code in (400, 404, 422):
        return OpenRouterInvalidRequestError(f"OpenRouter invalid request (HTTP {status_code}): {detail}")
    return OpenRouterInferenceError(f"OpenRouter request failed with HTTP {status_code}: {detail}")


def _extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON object from markdown fence or raw text."""
    if not text:
        return None
    cleaned = text.strip()

    # 1. Match ```json { ... } ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # 2. Match first outer { ... }
    match_braces = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match_braces:
        try:
            return json.loads(match_braces.group(1))
        except Exception:
            pass

    # 3. Direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None


def optimize_image_for_vision(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_dimension: int = 1536,
) -> Tuple[bytes, str]:
    """Optimize image dimensions and format to prevent HTTP 413 and excessive inference latency."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            orig_size = img.size
            if max(orig_size) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                fmt = "PNG" if mime_type.lower() == "image/png" else "JPEG"
                if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(buf, format=fmt, quality=88)
                optimized_bytes = buf.getvalue()
                out_mime = "image/png" if fmt == "PNG" else "image/jpeg"
                logger.info(
                    "[OpenRouter Vision] Resized image from %s to %s (%d bytes -> %d bytes)",
                    orig_size,
                    img.size,
                    len(image_bytes),
                    len(optimized_bytes),
                )
                return optimized_bytes, out_mime
    except Exception as exc:
        logger.debug("[OpenRouter Vision] Image optimization pass skipped: %s", exc)

    return image_bytes, mime_type

def encode_image_to_data_url(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_dimension: int = 1536,
) -> str:
    """Optimize and encode image bytes into a Base64 data URL."""
    opt_bytes, opt_mime = optimize_image_for_vision(image_bytes, mime_type, max_dimension)
    b64_encoded = base64.b64encode(opt_bytes).decode("utf-8")
    return f"data:{opt_mime};base64,{b64_encoded}"


# ==============================================================================
# Core OpenRouter Multimodal Chat Completion
# ==============================================================================

async def infer_openrouter_vision(
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout_seconds: Optional[float] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Execute multimodal vision chat completion via OpenRouter using PillSync Base64 approach.

    Returns:
        (raw_text_response, diagnostics_dict)
    """
    settings = get_settings()
    active_key = api_key or settings.openrouter_api_key
    if not active_key or not active_key.strip() or active_key.startswith("your_"):
        raise OpenRouterConfigError(
            "OPENROUTER_API_KEY is not configured in .env. "
            "Please obtain an API key from https://openrouter.ai/ and set OPENROUTER_API_KEY."
        )

    active_model = model_name or settings.openrouter_vision_model or "google/gemma-4-26b-a4b-it"
    timeout = timeout_seconds or settings.openrouter_timeout_seconds or 45.0
    endpoint = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

    # 1. Optimize image dimensions & encode to Base64 data URL
    data_url = encode_image_to_data_url(image_bytes, mime_type)


    # 3. Construct OpenAI-compatible multimodal payload
    payload = {
        "model": active_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                        },
                    },
                ],
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {active_key.strip()}",
        "HTTP-Referer": "https://truebasket.app",
        "X-Title": "TrueBasket Food Packaging Intelligence",
        "Content-Type": "application/json",
    }

    start_time = time.perf_counter()
    logger.info(
        "[OpenRouter Vision] Requesting model='%s' (image bytes: %d, mime: %s, timeout: %.1fs)",
        active_model,
        len(image_bytes),
        mime_type,
        timeout,
    )

    max_attempts = 3
    backoffs = [1.5, 3.0]
    last_exc: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if resp.status_code != 200:
                classified_err = _classify_http_error(resp.status_code, resp.text, active_key)
                # Transient error backoff
                if isinstance(classified_err, (OpenRouterServerError, OpenRouterRateLimitError)) and attempt < len(backoffs):
                    delay = backoffs[attempt]
                    logger.warning(
                        "[OpenRouter Vision] Transient %s on attempt %d/%d; retrying in %.1fs...",
                        type(classified_err).__name__,
                        attempt + 1,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    last_exc = classified_err
                    continue
                raise classified_err

            # Parse completion response
            body = resp.json()
            choices = body.get("choices") or []
            if not choices:
                raise OpenRouterEmptyResponseError("OpenRouter returned a 200 response with zero choices.")

            message = choices[0].get("message") or {}
            content = message.get("content") or ""
            if not content.strip():
                raise OpenRouterEmptyResponseError("OpenRouter model returned an empty content string.")

            diagnostics = {
                "provider": "openrouter",
                "model": active_model,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
                "usage": body.get("usage", {}),
                "finish_reason": choices[0].get("finish_reason"),
                "empty_response": False,
            }

            logger.info(
                "[OpenRouter Vision] Success in %.2fms (finish_reason: %s, prompt_tokens: %s, completion_tokens: %s)",
                latency_ms,
                diagnostics["finish_reason"],
                diagnostics["usage"].get("prompt_tokens"),
                diagnostics["usage"].get("completion_tokens"),
            )

            return content, diagnostics

        except httpx.TimeoutException as texc:
            last_exc = OpenRouterTimeoutError(f"OpenRouter request timed out after {timeout} seconds.")
            if attempt < len(backoffs):
                delay = backoffs[attempt]
                logger.warning("[OpenRouter Vision] Timeout on attempt %d; retrying in %.1fs...", attempt + 1, delay)
                await asyncio.sleep(delay)
                continue
            raise last_exc from texc

        except OpenRouterError:
            raise

        except Exception as exc:
            classified = _classify_http_error(500, str(exc), active_key)
            last_exc = classified
            if attempt < len(backoffs):
                await asyncio.sleep(backoffs[attempt])
                continue
            raise classified from exc

    if last_exc:
        raise last_exc
    raise OpenRouterInferenceError("OpenRouter vision request failed after retries.")


# ==============================================================================
# Text Inference Smoke Test (Verification)
# ==============================================================================

async def run_openrouter_text_smoke_test(
    prompt: str = 'Respond strictly with valid JSON: {"status": "ok", "provider": "openrouter"}',
) -> Dict[str, Any]:
    """Execute text-only chat completion to verify OpenRouter credentials and connectivity."""
    settings = get_settings()
    active_key = settings.openrouter_api_key
    if not active_key or not active_key.strip() or active_key.startswith("your_"):
        raise OpenRouterConfigError("OPENROUTER_API_KEY is not configured in .env.")

    active_model = settings.openrouter_vision_model or "google/gemma-3-27b-it"
    endpoint = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": active_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {active_key.strip()}",
        "HTTP-Referer": "https://truebasket.app",
        "X-Title": "TrueBasket Text Verification",
        "Content-Type": "application/json",
    }

    start_time = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(endpoint, json=payload, headers=headers)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    if resp.status_code != 200:
        raise _classify_http_error(resp.status_code, resp.text, active_key)

    body = resp.json()
    choices = body.get("choices") or []
    content = choices[0].get("message", {}).get("content", "") if choices else ""
    structured = _extract_json_from_response(content)

    return {
        "success": True,
        "provider": "openrouter",
        "model": active_model,
        "latency_ms": latency_ms,
        "raw_response": content,
        "structured_output": structured,
    }


# ==============================================================================
# Image Inference Smoke Test (Verification)
# ==============================================================================

async def run_openrouter_image_smoke_test(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute multimodal vision smoke test on an uploaded image."""
    test_prompt = prompt or (
        "You are a food package perception system. Inspect this image. "
        "Respond strictly with valid JSON:\n"
        "{\n"
        '  "brand": string or null,\n'
        '  "product_name": string or null,\n'
        '  "variant": string or null,\n'
        '  "package_size": string or null,\n'
        '  "visible_claims": [list of strings],\n'
        '  "unreadable_fields": [list of strings]\n'
        "}"
    )

    content, diagnostics = await infer_openrouter_vision(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=test_prompt,
    )

    structured = _extract_json_from_response(content)
    return {
        "success": True,
        "provider": "openrouter",
        "model": diagnostics["model"],
        "latency_ms": diagnostics["latency_ms"],
        "raw_response": content,
        "structured_output": structured,
        "diagnostics": diagnostics,
    }
