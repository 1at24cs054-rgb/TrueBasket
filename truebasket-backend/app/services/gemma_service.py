"""Gemma 4 LLM & Multimodal service integration.

Supports both official Google Developer API (via google-genai) and
OpenAI-compatible hosted endpoints (e.g. vLLM, Ollama, HuggingFace, AWS Bedrock proxy).
"""

import asyncio
import base64
import json
import logging
import re
import sys
import time
from typing import Any, Dict, Optional, Tuple
import httpx

from app.config import get_settings
from app.schemas import GemmaSmokeTestResponse

logger = logging.getLogger("truebasket.services.gemma")


# ==============================================================================
# Exceptions
# ==============================================================================

class GemmaError(Exception):
    """Base exception for Gemma 4 operations."""
    pass


class GemmaConfigError(GemmaError):
    """Raised when Gemma 4 configuration or credentials are missing."""
    pass


class GemmaAuthError(GemmaError):
    """Raised on authentication failure with the inference provider."""
    pass


class GemmaRateLimitError(GemmaError):
    """Raised when provider rate limit or quota is exceeded (HTTP 429)."""
    pass


class GemmaServerError(GemmaError):
    """Raised when inference provider encounters transient server errors (HTTP 500, 502, 503, 504)."""
    pass


class GemmaInvalidRequestError(GemmaError):
    """Raised when request payload or parameters are invalid (HTTP 400)."""
    pass


class GemmaInferenceError(GemmaError):
    """Raised when model inference fails or returns invalid output."""
    pass


class GemmaEmptyResponseError(GemmaInferenceError):
    """Raised when model returns an empty or whitespace-only response."""
    pass


class GemmaMultimodalUnsupportedError(GemmaError):
    """Raised if the configured endpoint or model does not support image inputs."""
    pass


# ==============================================================================
# Configuration Inspection Helper
# ==============================================================================

def inspect_gemma_configuration() -> Tuple[bool, Dict[str, Any]]:
    """Inspect current Gemma 4 configuration status without exposing secrets.

    Returns:
        (is_ready, details_dict)
    """
    settings = get_settings()
    provider = (settings.gemma_provider or "").lower().strip()

    info: Dict[str, Any] = {
        "provider": provider or "unknown",
        "model": settings.gemma_model,
        "configured": False,
        "multimodal_supported": True,
        "details": "",
        "setup_guide": (
            "Configure Gemma 4 in your .env file:\n"
            "Option 1 (Google Developer API / AI Studio):\n"
            "  GEMMA_PROVIDER=google\n"
            "  GEMMA_API_KEY=your_google_ai_studio_api_key\n"
            "  GEMMA_MODEL=gemma-4-26b-a4b-it (or gemma-4-12b-it)\n\n"
            "Option 2 (Hosted OpenAI-compatible endpoint / AWS Bedrock / vLLM):\n"
            "  GEMMA_PROVIDER=openai_compatible\n"
            "  GEMMA_API_BASE_URL=https://your-endpoint.com/v1\n"
            "  GEMMA_MODEL=gemma-4-model-name\n"
            "  GEMMA_API_KEY=optional_token\n"
        ),
    }

    if provider == "google":
        if settings.is_gemma_configured:
            info["configured"] = True
            info["details"] = f"Ready using Google GenAI API with model '{settings.gemma_model}'"
        else:
            info["details"] = (
                "GEMMA_API_KEY is not configured for provider 'google'. "
                "Get an API key from https://aistudio.google.com/ and set GEMMA_API_KEY in .env."
            )
    elif provider == "openai_compatible":
        if settings.is_gemma_configured:
            info["configured"] = True
            info["details"] = (
                f"Ready using OpenAI-compatible endpoint '{settings.gemma_api_base_url}' "
                f"with model '{settings.gemma_model}'"
            )
        else:
            info["details"] = (
                "GEMMA_API_BASE_URL is not set for provider 'openai_compatible'. "
                "Set GEMMA_API_BASE_URL in .env."
            )
    else:
        info["details"] = (
            f"Unsupported GEMMA_PROVIDER '{provider}'. Supported providers are: 'google', 'openai_compatible'."
        )

    return info["configured"], info


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse JSON from raw text or markdown code fence."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    candidate = match.group(1) if match else cleaned

    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


# ==============================================================================
# Text Inference Smoke Test
# ==============================================================================

async def run_gemma_text_smoke_test(
    prompt: Optional[str] = None,
) -> GemmaSmokeTestResponse:
    """Execute a minimal text-inference test asking Gemma 4 for structured output.

    Args:
        prompt: Custom test prompt or None for standard food verification prompt.

    Returns:
        GemmaSmokeTestResponse with output, latency, and parsed JSON.

    Raises:
        GemmaConfigError: When inference credentials/endpoints are missing.
        GemmaInferenceError: When model generation fails.
    """
    settings = get_settings()
    is_ready, config_info = inspect_gemma_configuration()

    if not is_ready:
        raise GemmaConfigError(
            f"Gemma 4 is not configured: {config_info['details']}\n\n{config_info['setup_guide']}"
        )

    test_prompt = prompt or (
        "Respond strictly with valid JSON. "
        "Analyze this food: 'TrueBasket Organic Muesli (Oats, Almonds, Flaxseeds)'. "
        "Output fields: 'product_name' (string), 'category' (string), 'protein_rich' (boolean), "
        "'primary_health_benefit' (string)."
    )

    provider = settings.gemma_provider.lower().strip()
    start_time = time.perf_counter()

    if provider == "google":
        response_text = await _infer_google_genai(
            model_name=settings.gemma_model,
            api_key=settings.gemma_api_key,
            prompt=test_prompt,
            temperature=settings.gemma_temperature,
            max_tokens=settings.gemma_max_output_tokens,
            timeout_seconds=settings.gemma_timeout_seconds,
        )
    elif provider == "openai_compatible":
        response_text = await _infer_openai_compatible(
            base_url=settings.gemma_api_base_url,
            api_key=settings.gemma_api_key,
            model_name=settings.gemma_model,
            prompt=test_prompt,
            temperature=settings.gemma_temperature,
            max_tokens=settings.gemma_max_output_tokens,
            timeout_seconds=settings.gemma_timeout_seconds,
        )
    else:
        raise GemmaConfigError(f"Unsupported provider: {provider}")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    structured = _extract_json(response_text)

    return GemmaSmokeTestResponse(
        success=True,
        provider=provider,
        model=settings.gemma_model,
        input_type="text",
        response_text=response_text,
        structured_output=structured,
        latency_ms=elapsed_ms,
    )


# ==============================================================================
# Multimodal Image Inference Smoke Test
# ==============================================================================

async def run_gemma_image_smoke_test(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    prompt: Optional[str] = None,
) -> GemmaSmokeTestResponse:
    """Execute a multimodal image inference smoke test on Gemma 4.

    Args:
        image_bytes: Raw binary bytes of food packaging image.
        mime_type: MIME type of the image (e.g. 'image/jpeg', 'image/png').
        prompt: Optional vision prompt.

    Returns:
        GemmaSmokeTestResponse with vision interpretation and metadata.
    """
    settings = get_settings()
    is_ready, config_info = inspect_gemma_configuration()

    if not is_ready:
        raise GemmaConfigError(
            f"Gemma 4 is not configured: {config_info['details']}\n\n{config_info['setup_guide']}"
        )

    test_prompt = prompt or (
        "Respond strictly with valid JSON. "
        "Inspect this food package image. Extract the following fields: "
        "'brand' (string or null), 'product_title' (string or null), "
        "'visible_ingredients' (list of strings), 'nutrition_highlights' (list of strings)."
    )

    provider = settings.gemma_provider.lower().strip()
    start_time = time.perf_counter()

    if provider == "google":
        response_text = await _infer_google_genai_multimodal(
            model_name=settings.gemma_model,
            api_key=settings.gemma_api_key,
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=test_prompt,
            temperature=settings.gemma_temperature,
            max_tokens=settings.gemma_max_output_tokens,
            timeout_seconds=settings.gemma_timeout_seconds,
        )
    elif provider == "openai_compatible":
        response_text = await _infer_openai_compatible_multimodal(
            base_url=settings.gemma_api_base_url,
            api_key=settings.gemma_api_key,
            model_name=settings.gemma_model,
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=test_prompt,
            temperature=settings.gemma_temperature,
            max_tokens=settings.gemma_max_output_tokens,
            timeout_seconds=settings.gemma_timeout_seconds,
        )
    else:
        raise GemmaConfigError(f"Unsupported provider: {provider}")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    structured = _extract_json(response_text)

    return GemmaSmokeTestResponse(
        success=True,
        provider=provider,
        model=settings.gemma_model,
        input_type="multimodal",
        response_text=response_text,
        structured_output=structured,
        latency_ms=elapsed_ms,
    )


def _extract_response_text(response: Any) -> str:
    """Extract clean response text from a Gemini/Gemma response object.

    Handles both standard models and reasoning models (which emit Part.thought).
    """
    if not response:
        return ""
    try:
        t = getattr(response, "text", None)
        if t and t.strip():
            return t
    except Exception:
        pass

    candidates = getattr(response, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        # Gather non-thought text first
        non_thought = [p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)]
        if non_thought and "".join(non_thought).strip():
            return "".join(non_thought)
        # Fallback to thought parts if valid JSON was emitted within thinking
        thought_parts = [p.text for p in parts if getattr(p, "text", None)]
        if thought_parts and "".join(thought_parts).strip():
            return "".join(thought_parts)
    return ""


def _classify_provider_error(exc: Exception, api_key: str = "") -> GemmaError:
    """Classify provider exception into specific domain error, sanitizing secrets."""
    err_msg = str(exc)
    if api_key and api_key in err_msg:
        err_msg = err_msg.replace(api_key, "[REDACTED]")

    low_msg = err_msg.lower()
    if any(k in err_msg for k in ["401", "403", "API_KEY_INVALID"]) or "unauthenticated" in low_msg or "permission" in low_msg:
        return GemmaAuthError(f"Authentication failed with inference provider: {err_msg}")
    if "429" in err_msg or "resource_exhausted" in low_msg or "rate limit" in low_msg:
        return GemmaRateLimitError(f"Provider rate limit or quota exceeded: {err_msg}")
    if any(k in err_msg for k in ["500", "502", "503", "504", "INTERNAL", "UNAVAILABLE"]):
        return GemmaServerError(f"Transient provider server error: {err_msg}")
    if "400" in err_msg or "invalid_argument" in low_msg:
        return GemmaInvalidRequestError(f"Invalid model request parameters: {err_msg}")
    if isinstance(exc, asyncio.TimeoutError):
        return GemmaInferenceError(f"Gemma 4 inference timed out: {err_msg}")
    if isinstance(exc, GemmaEmptyResponseError):
        return exc
    if isinstance(exc, GemmaError):
        return exc
    return GemmaInferenceError(f"Gemma 4 inference failed: {err_msg}")


# ==============================================================================
# Provider Implementations
# ==============================================================================

async def _infer_google_genai(
    model_name: str,
    api_key: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Call Google Developer API using google-genai SDK or direct REST API."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        loop = asyncio.get_running_loop()

        max_attempts = 3
        backoffs = [1.5, 3.0]
        last_classified_err: Optional[GemmaError] = None

        for attempt in range(max_attempts):
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                temperature=temperature,
                                max_output_tokens=max_tokens,
                            ),
                        ),
                    ),
                    timeout=timeout_seconds,
                )
                text = _extract_response_text(response)
                if not text or not text.strip():
                    raise GemmaEmptyResponseError("Google GenAI returned an empty response.")
                return text
            except Exception as exc:
                classified = _classify_provider_error(exc, api_key=api_key)
                last_classified_err = classified

                if isinstance(classified, (GemmaServerError, GemmaRateLimitError)) and attempt < len(backoffs):
                    delay = backoffs[attempt]
                    logger.warning(
                        "Transient error from Google GenAI on attempt %d/%d; retrying in %.1fs...",
                        attempt + 1,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                raise classified from exc

        if last_classified_err:
            raise last_classified_err
        raise GemmaInferenceError("Google GenAI text inference failed after retries.")

    except ImportError:
        return await _infer_google_rest_direct(
            model_name=model_name,
            api_key=api_key,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
        )
    except GemmaError:
        raise
    except Exception as exc:
        raise _classify_provider_error(exc, api_key=api_key) from exc


async def _infer_google_genai_multimodal(
    model_name: str,
    api_key: str,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Call Google Developer API with image Part for multimodal inspection."""
    # Ensure optimal token budget: Gemma 4 reasoning models emit internal thinking tokens
    # and require at least 4096 tokens to avoid running out of budget before emitting output.
    effective_max_tokens = max(max_tokens, 4096)

    try:
        from google import genai
        from google.genai import types

        # Ensure image is within optimal dimensions (max 1024px) for vision inference stability
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(image_bytes)) as pil_img:
                if max(pil_img.size) > 1024:
                    pil_img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    out_buf = io.BytesIO()
                    fmt = "PNG" if mime_type.lower() == "image/png" else "JPEG"
                    if fmt == "JPEG" and pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")
                    pil_img.save(out_buf, format=fmt, quality=88)
                    image_bytes = out_buf.getvalue()
                    mime_type = "image/png" if fmt == "PNG" else "image/jpeg"
        except Exception as opt_err:
            logger.debug("Image dimension optimization skipped: %s", opt_err)

        client = genai.Client(api_key=api_key)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        loop = asyncio.get_running_loop()

        max_attempts = 3
        backoffs = [1.5, 3.0]
        last_classified_err: Optional[GemmaError] = None

        for attempt in range(max_attempts):
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=model_name,
                            contents=[image_part, prompt],
                            config=types.GenerateContentConfig(
                                temperature=temperature,
                                max_output_tokens=effective_max_tokens,
                            ),
                        ),
                    ),
                    timeout=timeout_seconds,
                )
                text = _extract_response_text(response)
                if not text or not text.strip():
                    raise GemmaEmptyResponseError("Google GenAI returned an empty multimodal response.")
                return text
            except Exception as exc:
                classified = _classify_provider_error(exc, api_key=api_key)
                last_classified_err = classified

                if isinstance(classified, (GemmaServerError, GemmaRateLimitError)) and attempt < len(backoffs):
                    delay = backoffs[attempt]
                    logger.warning(
                        "Transient error from Google GenAI on attempt %d/%d (%s); retrying in %.1fs...",
                        attempt + 1,
                        max_attempts,
                        type(classified).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                raise classified from exc

        if last_classified_err:
            raise last_classified_err
        raise GemmaInferenceError("Gemma 4 multimodal inference failed after retries.")

    except GemmaError:
        raise
    except Exception as exc:
        raise _classify_provider_error(exc, api_key=api_key) from exc


async def _infer_google_rest_direct(
    model_name: str,
    api_key: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    """Direct REST fallback to Google Generative Language API via HTTPX."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"]
            raise GemmaInferenceError(f"Unexpected Google REST response structure: {data}")
        elif resp.status_code in (401, 403):
            raise GemmaAuthError(f"Google API authentication failed: {resp.text}")
        else:
            raise GemmaInferenceError(f"Google REST API HTTP {resp.status_code}: {resp.text}")


async def _infer_openai_compatible(
    base_url: str,
    api_key: Optional[str],
    model_name: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Call an OpenAI-compatible hosted endpoint (vLLM, Ollama, AWS Bedrock proxy)."""
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "")
                if not content or not content.strip():
                    raise GemmaEmptyResponseError("OpenAI-compatible endpoint returned an empty response.")
                return content
            raise GemmaInferenceError(f"Invalid choices payload from endpoint: {data}")
        elif resp.status_code in (401, 403):
            raise GemmaAuthError(f"Endpoint authentication failed (HTTP {resp.status_code}): {resp.text}")
        elif resp.status_code == 429:
            raise GemmaRateLimitError(f"Endpoint rate limit exceeded: {resp.text}")
        elif resp.status_code in (500, 502, 503, 504):
            raise GemmaServerError(f"Endpoint server error (HTTP {resp.status_code}): {resp.text}")
        elif resp.status_code == 400:
            raise GemmaInvalidRequestError(f"Invalid request to endpoint (HTTP 400): {resp.text}")
        else:
            raise GemmaInferenceError(f"Endpoint error (HTTP {resp.status_code}): {resp.text}")

    except httpx.TimeoutException as exc:
        raise GemmaInferenceError(f"Request to {endpoint} timed out after {timeout_seconds}s") from exc
    except httpx.RequestError as exc:
        raise GemmaInferenceError(f"Connection error to {endpoint}: {exc}") from exc


async def _infer_openai_compatible_multimodal(
    base_url: str,
    api_key: Optional[str],
    model_name: str,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Call an OpenAI-compatible vision endpoint with base64 encoded image."""
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64_image}"

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "")
                if not content or not content.strip():
                    raise GemmaEmptyResponseError("OpenAI-compatible vision endpoint returned an empty response.")
                return content
            raise GemmaInferenceError(f"Invalid choices payload: {data}")
        elif resp.status_code in (401, 403):
            raise GemmaAuthError(f"Endpoint authentication failed: {resp.text}")
        elif resp.status_code == 429:
            raise GemmaRateLimitError(f"Vision endpoint rate limit exceeded: {resp.text}")
        elif resp.status_code in (500, 502, 503, 504):
            raise GemmaServerError(f"Vision endpoint server error (HTTP {resp.status_code}): {resp.text}")
        elif resp.status_code == 400:
            raise GemmaInvalidRequestError(f"Invalid request to vision endpoint (HTTP 400): {resp.text}")
        else:
            raise GemmaInferenceError(f"Vision endpoint error (HTTP {resp.status_code}): {resp.text}")

    except httpx.TimeoutException as exc:
        raise GemmaInferenceError(f"Multimodal request timed out after {timeout_seconds}s") from exc
    except httpx.RequestError as exc:
        raise GemmaInferenceError(f"Connection error to vision endpoint: {exc}") from exc


# ==============================================================================
# CLI Runner for Local Smoke Testing
# ==============================================================================

async def _cli_smoke_test() -> None:
    """CLI runner to test Gemma 4 configuration and output."""
    print("=" * 70)
    print("TrueBasket — Gemma 4 Model Integration Smoke Test")
    print("=" * 70)

    is_ready, info = inspect_gemma_configuration()
    print(f"Provider:             {info['provider']}")
    print(f"Model Identifier:     {info['model']}")
    print(f"Configured:           {info['configured']}")
    print(f"Details:              {info['details']}")
    print("-" * 70)

    if not is_ready:
        print("\n[CONFIGURATION NOTICE]")
        print(info["details"])
        print("\n" + info["setup_guide"])
        print("Status: Gemma 4 inference is currently unconfigured (expected during initial setup).")
        return

    print("Attempting text inference smoke test...")
    try:
        result = await run_gemma_text_smoke_test()
        print(f"\n[SUCCESS] Response received in {result.latency_ms}ms:")
        print(result.response_text)
        if result.structured_output:
            print(f"\n[PARSED STRUCTURED JSON]:\n{json.dumps(result.structured_output, indent=2)}")
    except Exception as exc:
        print(f"\n[INFERENCE FAILED] {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_cli_smoke_test())
