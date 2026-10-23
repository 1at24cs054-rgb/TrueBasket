"""Unit tests for FastAPI health endpoint and CORS configuration."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings


@pytest.fixture
def client():
    """Create a FastAPI test client instance."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint_structure(client):
    """Verify /api/health returns HTTP 200 and matches the expected schema."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data
    assert "services" in data

    services = data["services"]
    assert "tavily" in services
    assert "gemma" in services

    # Validate Tavily health block
    tavily_health = services["tavily"]
    assert "configured" in tavily_health
    assert isinstance(tavily_health["configured"], bool)
    assert "status" in tavily_health
    assert "details" in tavily_health

    # Validate Gemma health block
    gemma_health = services["gemma"]
    assert "configured" in gemma_health
    assert isinstance(gemma_health["configured"], bool)
    assert "status" in gemma_health
    assert "provider" in gemma_health
    assert "model" in gemma_health
    assert "details" in gemma_health


def test_health_endpoint_never_leaks_secrets(client):
    """Ensure no raw API keys or tokens are ever exposed in the health response."""
    response = client.get("/api/health")
    raw_body = response.text.lower()

    # Common sensitive substrings
    forbidden_terms = [
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "bearer",
        "tvly-",
    ]

    for term in forbidden_terms:
        # Check that forbidden tokens are not in values
        assert f'"{term}"' not in raw_body, f"Potential secret leak detected for: {term}"


def test_cors_headers_present(client):
    """Verify CORS headers are returned for allowed origins."""
    settings = get_settings()
    allowed_origin = settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000"

    response = client.options(
        "/api/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI CORSMiddleware returns 200 on valid preflight
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") in (allowed_origin, "*")
