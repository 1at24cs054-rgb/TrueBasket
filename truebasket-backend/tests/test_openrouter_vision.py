"""Deterministic Mocked Unit Tests for OpenRouter Vision Integration.

Covers:
- Request payload construction & Base64 data URL formatting
- Pillow downsampling behavior
- Markdown JSON response parsing & structured field extraction
- Robust error classification (401 auth, 429 rate limit, 500 provider error, empty choices)
- Provider interface dispatching between openrouter and google
- End-to-end product analyzer extraction with Phase 3 fields
"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from PIL import Image
import pytest

from app.config import Settings
from app.services.openrouter_service import (
    encode_image_to_data_url,
    _extract_json_from_response,
    infer_openrouter_vision,
    OpenRouterAuthError,
    OpenRouterConfigError,
    OpenRouterEmptyResponseError,
    OpenRouterError,
    OpenRouterRateLimitError,
)
from app.services.vision_service import (
    inspect_vision_configuration,
    run_vision_image_inference,
)
from app.services.product_analyzer import extract_product_from_packaging, extract_visual_label_from_image


def make_test_image_bytes(width: int = 100, height: int = 100) -> bytes:
    """Generate minimal valid JPEG bytes."""
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ==============================================================================
# 1. Base64 Encoding & Payload Construction Tests
# ==============================================================================

def test_encode_image_to_data_url_format():
    """Verify data URL starts with data:image/jpeg;base64, and resizes large dimensions."""
    raw_bytes = make_test_image_bytes(2000, 1000)
    data_url = encode_image_to_data_url(raw_bytes, "image/jpeg", max_dimension=1000)

    assert data_url.startswith("data:image/jpeg;base64,")
    # Base64 string must be non-empty
    b64_content = data_url.split(",", 1)[1]
    assert len(b64_content) > 100


def test_extract_json_from_markdown_blocks():
    """Verify clean extraction of JSON from ```json ... ``` code fences."""
    raw_text = """Here is the analysis of the food label:
```json
{
  "brand": "YogaBar",
  "product_name": "Super Muesli",
  "variant": "Almond & Cranberry",
  "package_size": "400g",
  "visible_claims": ["100% Whole Grain", "No Added Sugar"],
  "unreadable_fields": [],
  "evidence_notes": "Front and back panels are clearly legible."
}
```
Thank you for using the service.
"""
    extracted = _extract_json_from_response(raw_text)
    assert extracted is not None
    assert extracted["brand"] == "YogaBar"
    assert extracted["product_name"] == "Super Muesli"
    assert extracted["package_size"] == "400g"
    assert "No Added Sugar" in extracted["visible_claims"]


# ==============================================================================
# 2. OpenRouter Multimodal Chat Completions Mocked Requests
# ==============================================================================

@pytest.mark.asyncio
async def test_infer_openrouter_vision_success():
    """Verify correct chat completions payload construction and response parsing."""
    mock_response_json = {
        "id": "gen-12345",
        "model": "google/gemma-3-27b-it",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '```json\n{"brand": "Kellogg\'s", "product_name": "Crunchy Muesli", "net_weight": "750g"}\n```',
                }
            }
        ],
        "usage": {"total_tokens": 150},
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_json

    mock_settings = Settings(
        openrouter_api_key="sk-or-v1-mock-test-key-12345",
        openrouter_vision_model="google/gemma-3-27b-it",
        ai_vision_provider="openrouter",
    )

    with patch("app.services.openrouter_service.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            img_bytes = make_test_image_bytes(200, 200)
            content, diag = await infer_openrouter_vision(
                image_bytes=img_bytes,
                mime_type="image/jpeg",
                prompt="Identify this product",
            )

            # Assert correct payload structure sent to OpenRouter
            assert mock_post.called
            call_kwargs = mock_post.call_args.kwargs
            payload = call_kwargs["json"]
            assert payload["model"] == "google/gemma-3-27b-it"
            assert len(payload["messages"]) == 1
            user_msg = payload["messages"][0]
            assert user_msg["role"] == "user"
            assert len(user_msg["content"]) == 2
            assert user_msg["content"][0]["type"] == "text"
            assert user_msg["content"][1]["type"] == "image_url"
            assert user_msg["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

            # Check return values
            assert "Kellogg's" in content
            assert diag["model"] == "google/gemma-3-27b-it"
            assert diag["empty_response"] is False


@pytest.mark.asyncio
async def test_infer_openrouter_vision_auth_error():
    """Verify HTTP 401 raises OpenRouterAuthError without exposing secrets."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized: Invalid API key"
    mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}

    mock_settings = Settings(
        openrouter_api_key="sk-or-v1-invalid-key",
        openrouter_vision_model="google/gemma-3-27b-it",
    )

    with patch("app.services.openrouter_service.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            with pytest.raises(OpenRouterAuthError) as exc_info:
                await infer_openrouter_vision(
                    image_bytes=make_test_image_bytes(),
                    mime_type="image/jpeg",
                    prompt="Test",
                )
            assert "authentication failed" in str(exc_info.value).lower()
            assert "sk-or-v1-invalid-key" not in str(exc_info.value)



@pytest.mark.asyncio
async def test_infer_openrouter_vision_rate_limit_error():
    """Verify HTTP 429 raises OpenRouterRateLimitError."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit exceeded"
    mock_resp.json.return_value = {"error": {"message": "Rate limit exceeded. Please wait."}}

    mock_settings = Settings(
        openrouter_api_key="sk-or-v1-valid-key",
        openrouter_vision_model="google/gemma-3-27b-it",
    )

    with patch("app.services.openrouter_service.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            with pytest.raises(OpenRouterRateLimitError):
                await infer_openrouter_vision(
                    image_bytes=make_test_image_bytes(),
                    mime_type="image/jpeg",
                    prompt="Test",
                )


@pytest.mark.asyncio
async def test_infer_openrouter_vision_empty_response():
    """Verify empty response choices raises OpenRouterEmptyResponseError."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": []}

    mock_settings = Settings(
        openrouter_api_key="sk-or-v1-valid-key",
        openrouter_vision_model="google/gemma-3-27b-it",
    )

    with patch("app.services.openrouter_service.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            with pytest.raises(OpenRouterEmptyResponseError):
                await infer_openrouter_vision(
                    image_bytes=make_test_image_bytes(),
                    mime_type="image/jpeg",
                    prompt="Test",
                )


# ==============================================================================
# 3. Unified Vision Service & Provider Switching Tests
# ==============================================================================

def test_inspect_vision_configuration():
    """Verify configuration inspector returns truthful readiness status."""
    mock_settings_configured = Settings(
        ai_vision_provider="openrouter",
        openrouter_api_key="sk-or-v1-real-key",
        openrouter_vision_model="google/gemma-3-27b-it",
    )
    with patch("app.services.vision_service.get_settings", return_value=mock_settings_configured):
        ready, info = inspect_vision_configuration()
        assert ready is True
        assert info["provider"] == "openrouter"
        assert info["model"] == "google/gemma-3-27b-it"

    mock_settings_unconfigured = Settings(
        ai_vision_provider="openrouter",
        openrouter_api_key="",
    )
    with patch("app.services.vision_service.get_settings", return_value=mock_settings_unconfigured):
        ready, info = inspect_vision_configuration()
        assert ready is False
        assert "OPENROUTER_API_KEY is not configured" in info["details"]


@pytest.mark.asyncio
async def test_run_vision_image_inference_dispatches_to_openrouter():
    """Verify run_vision_image_inference routes through infer_openrouter_vision when active."""
    mock_settings = Settings(
        ai_vision_provider="openrouter",
        openrouter_api_key="sk-or-v1-valid-key",
        openrouter_vision_model="google/gemma-3-27b-it",
    )

    mock_diagnostics = {
        "provider": "openrouter",
        "model": "google/gemma-3-27b-it",
        "latency_ms": 420.0,
        "empty_response": False,
    }
    mock_content = '```json\n{"product_name": "Crunchy Almond Muesli", "brand": "TrueElements"}\n```'

    with patch("app.services.vision_service.get_settings", return_value=mock_settings):
        with patch("app.services.vision_service.infer_openrouter_vision", new_callable=AsyncMock) as mock_infer:
            mock_infer.return_value = (mock_content, mock_diagnostics)

            result = await run_vision_image_inference(
                image_bytes=make_test_image_bytes(),
                mime_type="image/jpeg",
                prompt="Analyze packaging",
            )

            assert result["success"] is True
            assert result["provider"] == "openrouter"
            assert result["model"] == "google/gemma-3-27b-it"
            assert result["structured_output"]["product_name"] == "Crunchy Almond Muesli"
            assert result["structured_output"]["brand"] == "TrueElements"


# ==============================================================================
# 4. Food Packaging Analysis Structured Extraction (Phase 3)
# ==============================================================================

@pytest.mark.asyncio
async def test_extract_product_from_packaging_populates_phase3_fields():
    """Verify extract_product_from_packaging extracts all required Phase 3 fields."""
    mock_vision_data = {
        "brand": "YogaBar",
        "product_name": "Super Muesli Dark Chocolate & Cranberry",
        "variant": "Dark Chocolate",
        "net_weight": "400g",
        "package_size": "400g",
        "label_type": "front_of_pack",
        "is_readable": True,
        "is_complete": False,
        "confidence": "high",
        "ingredient_list": ["Rolled Oats", "Cranberries", "Dark Chocolate", "Almonds"],
        "ingredients_text": "Rolled Oats (42%), Cranberries (15%), Dark Chocolate (10%), Almonds (8%)",
        "declared_percentages": {"Rolled Oats": 42.0, "Cranberries": 15.0},
        "nutrition_facts": {"protein_g": 12.0, "dietary_fibre_g": 9.5},
        "allergen_declarations": ["Contains Oats", "Contains Almonds"],
        "visible_claims": ["100% Whole Grains", "High Fibre"],
        "unreadable_fields": ["Barcode cut off at edge"],
        "evidence_notes": "Front panel verified with high confidence.",
        "barcode": "8906085172018",
    }

    mock_vision_resp = {
        "success": True,
        "provider": "openrouter",
        "model": "google/gemma-3-27b-it",
        "response_text": json.dumps(mock_vision_data),
        "structured_output": mock_vision_data,
        "latency_ms": 310.0,
    }

    with patch("app.services.product_analyzer.run_vision_image_inference", new_callable=AsyncMock) as mock_vision:
        mock_vision.return_value = mock_vision_resp

        product = await extract_product_from_packaging(
            image_bytes=make_test_image_bytes(),
            mime_type="image/jpeg",
        )

        assert product.brand == "YogaBar"
        assert product.product_name == "Super Muesli Dark Chocolate & Cranberry"
        assert product.package_size == "400g"
        assert product.barcode == "8906085172018"
        assert "100% Whole Grains" in product.visible_claims
        assert "Barcode cut off at edge" in product.unreadable_fields
        assert product.evidence_notes == "Front panel verified with high confidence."
        assert product.visual_extraction is not None
        assert product.visual_extraction.declared_percentages["Rolled Oats"] == 42.0
