"""Unit tests for Gemma 4 service integration and configuration inspection."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.config import get_settings
from app.services.gemma_service import (
    GemmaConfigError,
    _extract_json,
    inspect_gemma_configuration,
    run_gemma_text_smoke_test,
)


def test_inspect_gemma_configuration_when_unconfigured():
    """Verify inspection reports missing configuration without secrets."""
    settings = get_settings()
    original_key = settings.gemma_api_key

    try:
        settings.gemma_api_key = None
        settings.gemma_provider = "google"

        is_ready, info = inspect_gemma_configuration()
        assert is_ready is False
        assert info["configured"] is False
        assert "GEMMA_API_KEY is not configured" in info["details"]
        assert "setup_guide" in info
        assert "api_key" not in info["details"].lower() or "not configured" in info["details"]
    finally:
        settings.gemma_api_key = original_key


def test_extract_json_utilities():
    """Verify JSON extractor correctly parses raw text and markdown fences."""
    # Test 1: Markdown code fence
    markdown_sample = """Here is the analysis:
```json
{
  "product_name": "TrueBasket Muesli",
  "score": 9.5
}
```
Hope this helps!"""
    res = _extract_json(markdown_sample)
    assert res is not None
    assert res["product_name"] == "TrueBasket Muesli"
    assert res["score"] == 9.5

    # Test 2: Raw JSON string
    raw_sample = '{"brand": "YogaBar", "healthy": true}'
    res2 = _extract_json(raw_sample)
    assert res2 is not None
    assert res2["brand"] == "YogaBar"
    assert res2["healthy"] is True

    # Test 3: Non-JSON plain text
    plain_sample = "This is simply text with no json."
    assert _extract_json(plain_sample) is None


@pytest.mark.asyncio
async def test_run_gemma_text_smoke_test_raises_config_error_when_missing():
    """Verify smoke test raises GemmaConfigError when unconfigured."""
    settings = get_settings()
    original_key = settings.gemma_api_key

    try:
        settings.gemma_api_key = None
        settings.gemma_provider = "google"

        with pytest.raises(GemmaConfigError) as exc_info:
            await run_gemma_text_smoke_test()

        assert "Gemma 4 is not configured" in str(exc_info.value)
    finally:
        settings.gemma_api_key = original_key


@pytest.mark.asyncio
async def test_run_gemma_openai_compatible_mock():
    """Verify OpenAI-compatible endpoint provider handling."""
    settings = get_settings()
    orig_provider = settings.gemma_provider
    orig_url = settings.gemma_api_base_url
    orig_key = settings.gemma_api_key

    settings.gemma_provider = "openai_compatible"
    settings.gemma_api_base_url = "http://localhost:11434/v1"
    settings.gemma_api_key = "dummy-token"

    fake_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"product_name": "TrueBasket Muesli", "protein_rich": true}',
                }
            }
        ]
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=fake_response,
        request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
    )

    try:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await run_gemma_text_smoke_test(prompt="Test prompt")

            assert result.success is True
            assert result.provider == "openai_compatible"
            assert result.structured_output is not None
            assert result.structured_output["product_name"] == "TrueBasket Muesli"
            assert result.structured_output["protein_rich"] is True
            assert result.latency_ms >= 0
    finally:
        settings.gemma_provider = orig_provider
        settings.gemma_api_base_url = orig_url
        settings.gemma_api_key = orig_key
