"""Tests for Gemma 4 provider error classification, transient retries, and failure modes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.gemma_service import (
    GemmaAuthError,
    GemmaEmptyResponseError,
    GemmaInvalidRequestError,
    GemmaRateLimitError,
    GemmaServerError,
    _classify_provider_error,
    _extract_response_text,
    _infer_google_genai,
    _infer_google_genai_multimodal,
)


def test_classify_provider_error_auth():
    err = _classify_provider_error(Exception("401 Unauthorized with API key secret-key-123"), api_key="secret-key-123")
    assert isinstance(err, GemmaAuthError)
    assert "secret-key-123" not in str(err)
    assert "[REDACTED]" in str(err)


def test_classify_provider_error_rate_limit():
    err = _classify_provider_error(Exception("429 RESOURCE_EXHAUSTED quota exceeded"))
    assert isinstance(err, GemmaRateLimitError)


def test_classify_provider_error_server_error():
    err = _classify_provider_error(Exception("503 Service Unavailable: backend overloaded"))
    assert isinstance(err, GemmaServerError)

    err500 = _classify_provider_error(Exception("500 INTERNAL server error occurred"))
    assert isinstance(err500, GemmaServerError)


def test_classify_provider_error_invalid_request():
    err = _classify_provider_error(Exception("400 INVALID_ARGUMENT: thinking_budget not supported"))
    assert isinstance(err, GemmaInvalidRequestError)


def test_extract_response_text_with_thought_parts():
    mock_resp = MagicMock()
    mock_resp.text = None

    p0 = MagicMock()
    p0.thought = True
    p0.text = "Thinking about muesli calories and nutrients..."

    p1 = MagicMock()
    p1.thought = False
    p1.text = '{"brand": "YogaBar", "product_name": "Super Muesli"}'

    cand = MagicMock()
    cand.content.parts = [p0, p1]
    mock_resp.candidates = [cand]

    text = _extract_response_text(mock_resp)
    assert '{"brand": "YogaBar"' in text
    assert "Thinking about" not in text


def test_extract_response_text_empty_returns_empty_string():
    mock_resp = MagicMock()
    mock_resp.text = ""
    mock_resp.candidates = []
    assert _extract_response_text(mock_resp) == ""


@pytest.mark.asyncio
async def test_infer_google_genai_empty_response_raises_empty_response_error():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_resp.candidates = []
        mock_client.models.generate_content.return_value = mock_resp

        with pytest.raises(GemmaEmptyResponseError) as exc_info:
            await _infer_google_genai(
                model_name="gemma-4",
                api_key="fake-key",
                prompt="hello",
                temperature=0.1,
                max_tokens=100,
                timeout_seconds=5.0,
            )
        assert "empty response" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_infer_google_genai_multimodal_retries_transient_500():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.text = '{"brand": "Kellogg\'s"}'

        # Fail with 500 on attempt 1, succeed on attempt 2
        mock_client.models.generate_content.side_effect = [
            Exception("500 INTERNAL server error"),
            mock_resp,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await _infer_google_genai_multimodal(
                model_name="gemma-4-26b-a4b-it",
                api_key="test-api-key",
                image_bytes=b"dummy",
                mime_type="image/jpeg",
                prompt="extract",
                temperature=0.1,
                max_tokens=1024,
                timeout_seconds=5.0,
            )

            assert '{"brand": "Kellogg\'s"}' in result
            assert mock_client.models.generate_content.call_count == 2
            mock_sleep.assert_called_once_with(1.5)


@pytest.mark.asyncio
async def test_infer_google_genai_multimodal_does_not_retry_400():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.models.generate_content.side_effect = Exception("400 INVALID_ARGUMENT: unsupported parameter")

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(GemmaInvalidRequestError):
                await _infer_google_genai_multimodal(
                    model_name="gemma-4-26b-a4b-it",
                    api_key="test-api-key",
                    image_bytes=b"dummy",
                    mime_type="image/jpeg",
                    prompt="extract",
                    temperature=0.1,
                    max_tokens=1024,
                    timeout_seconds=5.0,
                )

            # Never retry permanent 400 errors
            assert mock_client.models.generate_content.call_count == 1
            mock_sleep.assert_not_called()
