"""Tavily Search API service client for asynchronous web search."""

import asyncio
import logging
import sys
import time
from typing import Any, Dict, List, Optional
import httpx

from app.config import get_settings
from app.schemas import TavilySearchResponse, TavilySearchResultItem

logger = logging.getLogger("truebasket.services.web_search")


# ==============================================================================
# Exceptions
# ==============================================================================

class TavilyError(Exception):
    """Base exception for Tavily search operations."""
    pass


class TavilyConfigError(TavilyError):
    """Raised when the Tavily API key is missing or invalid in configuration."""
    pass


class TavilyAuthError(TavilyError):
    """Raised when authentication against Tavily fails (e.g. invalid API key)."""
    pass


class TavilyQuotaExceededError(TavilyError):
    """Raised when rate limits or plan quotas have been exhausted."""
    pass


class TavilyTimeoutError(TavilyError):
    """Raised when Tavily request exceeds configured timeout."""
    pass


class TavilyApiError(TavilyError):
    """Raised when Tavily API returns a client/server error or invalid payload."""
    pass


# ==============================================================================
# Service Implementation
# ==============================================================================

async def search_tavily(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    include_images: bool = False,
) -> TavilySearchResponse:
    """Execute an asynchronous web search using the official Tavily Search API.

    Args:
        query: Search query string (e.g. food product, ingredients, brands).
        max_results: Number of results to request (capped by settings limit).
        search_depth: 'basic' for rapid search, 'advanced' for deep search.
        include_domains: Optional list of domains to filter results by.
        exclude_domains: Optional list of domains to exclude.
        include_images: Whether to request product packaging images from Tavily.

    Returns:
        TavilySearchResponse containing preserved titles, URLs, snippets, images, and metadata.
    """
    settings = get_settings()

    # Guard: Configuration verification
    if not settings.is_tavily_configured:
        raise TavilyConfigError(
            "TAVILY_API_KEY is not configured. "
            "Please obtain an API key from https://tavily.com/ and set TAVILY_API_KEY in your .env file."
        )

    # Sanitize and bound parameters
    bounded_max_results = max(1, min(max_results, settings.tavily_max_results_limit))
    normalized_depth = search_depth.lower() if search_depth.lower() in {"basic", "advanced"} else "basic"

    request_payload: Dict[str, Any] = {
        "api_key": settings.tavily_api_key,
        "query": query.strip(),
        "search_depth": normalized_depth,
        "max_results": bounded_max_results,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": include_images,
    }

    if include_domains:
        request_payload["include_domains"] = include_domains
    if exclude_domains:
        request_payload["exclude_domains"] = exclude_domains

    endpoint_url = f"{settings.tavily_api_base_url.rstrip('/')}/search"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"TrueBasket-Backend/{settings.app_version}",
    }

    start_time = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=settings.tavily_timeout_seconds) as client:
            response = await client.post(
                endpoint_url,
                json=request_payload,
                headers=headers,
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Handle HTTP status codes
        if response.status_code == 200:
            data = response.json()
            raw_results = data.get("results", [])
            raw_images = data.get("images", [])

            parsed_items: List[TavilySearchResultItem] = []
            for item in raw_results:
                parsed_items.append(
                    TavilySearchResultItem(
                        title=str(item.get("title") or "Untitled"),
                        url=str(item.get("url") or ""),
                        content=str(item.get("content") or "").strip(),
                        score=float(item["score"]) if item.get("score") is not None else None,
                        published_date=str(item["published_date"]) if item.get("published_date") else None,
                    )
                )

            parsed_images: List[str] = [
                str(u) for u in raw_images if u and str(u).startswith("http")
            ]

            return TavilySearchResponse(
                query=query,
                results_count=len(parsed_items),
                results=parsed_items,
                images=parsed_images,
                response_time_ms=elapsed_ms,
            )

        elif response.status_code in (401, 403):
            raise TavilyAuthError(
                f"Tavily authentication failed (HTTP {response.status_code}). "
                "Verify that TAVILY_API_KEY in your .env file is active and valid."
            )
        elif response.status_code == 429:
            raise TavilyQuotaExceededError(
                "Tavily search rate limit or monthly quota exceeded (HTTP 429). "
                "Check your Tavily account dashboard at https://app.tavily.com/."
            )
        elif 400 <= response.status_code < 500:
            detail_msg = response.text[:200]
            raise TavilyApiError(f"Tavily API client error (HTTP {response.status_code}): {detail_msg}")
        else:
            raise TavilyApiError(f"Tavily API server error (HTTP {response.status_code}).")

    except httpx.TimeoutException as exc:
        raise TavilyTimeoutError(
            f"Tavily search timed out after {settings.tavily_timeout_seconds}s for query: '{query}'"
        ) from exc
    except httpx.RequestError as exc:
        raise TavilyApiError(f"Network error while connecting to Tavily: {exc}") from exc


# ==============================================================================
# CLI Smoke Test Runner
# ==============================================================================

async def _cli_smoke_test(query: str = "muesli ingredients nutrition label India") -> None:
    """CLI test query runner to show actual retrieved URLs and snippets."""
    print("=" * 70)
    print("TrueBasket — Tavily Search API Smoke Test")
    print(f"Target Query: {query}")
    print("=" * 70)

    try:
        response = await search_tavily(query=query, max_results=5)
        print(f"\n[SUCCESS] Retrieved {response.results_count} live results in {response.response_time_ms}ms:\n")
        for idx, result in enumerate(response.results, 1):
            print(f"[{idx}] {result.title}")
            print(f"    URL: {result.url}")
            if result.score is not None:
                print(f"    Relevance Score: {result.score:.4f}")
            if result.published_date:
                print(f"    Published: {result.published_date}")
            snippet = result.content[:180] + ("..." if len(result.content) > 180 else "")
            print(f"    Snippet: {snippet}")
            print("-" * 70)

    except TavilyConfigError as e:
        print(f"\n[CONFIGURATION NOTICE] {e}")
        print("-> Status: Tavily Search is currently unconfigured (expected during initial setup).")
        sys.exit(0)
    except TavilyAuthError as e:
        print(f"\n[AUTHENTICATION ERROR] {e}")
        sys.exit(1)
    except TavilyQuotaExceededError as e:
        print(f"\n[QUOTA EXCEEDED] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[SEARCH FAILED] {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_q = sys.argv[1] if len(sys.argv) > 1 else "muesli ingredients nutrition label India"
    asyncio.run(_cli_smoke_test(test_q))
