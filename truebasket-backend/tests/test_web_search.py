"""Unit and integration tests for Tavily search service."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.config import get_settings
from app.services.web_search import (
    TavilyAuthError,
    TavilyConfigError,
    TavilyQuotaExceededError,
    TavilyTimeoutError,
    search_tavily,
)


@pytest.mark.asyncio
async def test_search_tavily_unconfigured_raises_config_error():
    """Ensure search_tavily raises TavilyConfigError when API key is missing."""
    settings = get_settings()
    original_key = settings.tavily_api_key

    try:
        settings.tavily_api_key = None
        with pytest.raises(TavilyConfigError) as exc_info:
            await search_tavily(query="muesli ingredients")
        assert "TAVILY_API_KEY is not configured" in str(exc_info.value)
    finally:
        settings.tavily_api_key = original_key


@pytest.mark.asyncio
async def test_search_tavily_success_parsing():
    """Verify structured result parsing preserves title, url, snippet and metadata."""
    settings = get_settings()
    original_key = settings.tavily_api_key
    settings.tavily_api_key = "tvly-test-valid-key"

    fake_payload = {
        "results": [
            {
                "title": "Healthy Oats & Nut Muesli Ingredients",
                "url": "https://example.com/muesli-nutrition",
                "content": "Rolled oats (54%), roasted almonds, flax seeds, and zero added refined sugar.",
                "score": 0.942,
                "published_date": "2024-03-15",
            },
            {
                "title": "Breakfast Cereals Standards in India - FSSAI",
                "url": "https://example.org/fssai-cereals",
                "content": "Regulatory guidelines on labeling for dietary fiber and fortified breakfast cereals.",
                "score": 0.815,
                "published_date": None,
            },
        ]
    }

    mock_response = httpx.Response(
        status_code=200,
        json=fake_payload,
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )

    try:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await search_tavily(query="muesli nutrition India", max_results=2)

            assert response.results_count == 2
            assert len(response.results) == 2

            first = response.results[0]
            assert first.title == "Healthy Oats & Nut Muesli Ingredients"
            assert first.url == "https://example.com/muesli-nutrition"
            assert "Rolled oats (54%)" in first.content
            assert first.score == 0.942
            assert first.published_date == "2024-03-15"

            second = response.results[1]
            assert second.score == 0.815
            assert second.published_date is None
    finally:
        settings.tavily_api_key = original_key


@pytest.mark.asyncio
async def test_search_tavily_auth_error_handling():
    """Verify HTTP 401 raises TavilyAuthError."""
    settings = get_settings()
    original_key = settings.tavily_api_key
    settings.tavily_api_key = "tvly-invalid-key"

    mock_response = httpx.Response(
        status_code=401,
        json={"detail": "Unauthorized: invalid api key"},
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )

    try:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(TavilyAuthError) as exc_info:
                await search_tavily(query="muesli")
            assert "authentication failed" in str(exc_info.value).lower()
    finally:
        settings.tavily_api_key = original_key


@pytest.mark.asyncio
async def test_search_tavily_quota_exceeded_handling():
    """Verify HTTP 429 raises TavilyQuotaExceededError."""
    settings = get_settings()
    original_key = settings.tavily_api_key
    settings.tavily_api_key = "tvly-active-key"

    mock_response = httpx.Response(
        status_code=429,
        text="Rate limit exceeded",
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )

    try:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(TavilyQuotaExceededError) as exc_info:
                await search_tavily(query="muesli")
            assert "quota exceeded" in str(exc_info.value).lower()
    finally:
        settings.tavily_api_key = original_key


@pytest.mark.asyncio
async def test_search_tavily_timeout_handling():
    """Verify request timeout raises TavilyTimeoutError."""
    settings = get_settings()
    original_key = settings.tavily_api_key
    settings.tavily_api_key = "tvly-active-key"

    try:
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
            with pytest.raises(TavilyTimeoutError) as exc_info:
                await search_tavily(query="muesli")
            assert "timed out" in str(exc_info.value).lower()
    finally:
        settings.tavily_api_key = original_key
