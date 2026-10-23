"""Integration tests verifying compatibility with the React/Vite frontend contract."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas import (
    AdditiveAnalysis,
    AllergenAnalysis,
    FibreWholeGrainAnalysis,
    IngredientAnalysis,
    OilAnalysis,
    OriginalProduct,
    ProductAnalysisResponse,
    SugarAnalysis,
)


@pytest.fixture
def client():
    """Create a FastAPI test client instance."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_routes(client):
    """Verify both /health and /api/health return HTTP 200 with system status."""
    res_root_health = client.get("/health")
    assert res_root_health.status_code == 200
    assert res_root_health.json()["status"] in ("ok", "degraded")

    res_api_health = client.get("/api/health")
    assert res_api_health.status_code == 200
    assert res_api_health.json()["status"] == res_root_health.json()["status"]
    assert res_api_health.json()["app_name"] == res_root_health.json()["app_name"]


def test_get_prices_contract(client):
    """Verify GET /api/prices returns the frontend-specified listings schema."""
    response = client.get("/api/prices")
    assert response.status_code == 200
    data = response.json()
    assert "listings" in data
    assert isinstance(data["listings"], list)

    # Test with typical frontend query parameters
    param_response = client.get(
        "/api/prices?barcode=8901058851298&query=Kellogg%27s%20Muesli%20500%20g&pincode=560001"
    )
    assert param_response.status_code == 200
    assert "listings" in param_response.json()


def test_cors_frontend_origins(client):
    """Verify CORS preflight headers for Vite dev server origins (localhost and 127.0.0.1)."""
    for origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
        response = client.options(
            "/api/prices",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 204)
        assert response.headers.get("access-control-allow-origin") in (origin, "*")


def test_original_product_frontend_aliases():
    """Verify OriginalProduct populates name and quantity for frontend consumption."""
    prod = OriginalProduct(
        brand="Kellogg's",
        product_name="Muesli Fruit & Nut",
        net_weight="500 g",
        barcode="8901058851298",
    )
    data = prod.model_dump()
    assert data["brand"] == "Kellogg's"
    assert data["product_name"] == "Muesli Fruit & Nut"
    assert data["name"] == "Muesli Fruit & Nut"
    assert data["net_weight"] == "500 g"
    assert data["quantity"] == "500 g"
    assert data["barcode"] == "8901058851298"


def test_analyze_image_accepts_frontend_parameters(client):
    """Verify POST /api/products/analyze-image accepts frontend form values without validation errors."""
    mock_resp = ProductAnalysisResponse(
        original_product=OriginalProduct(
            brand="Kellogg's",
            product_name="Muesli Fruit & Nut",
            net_weight="500 g",
            barcode="8901058851298",
        ),
        ingredient_analysis=IngredientAnalysis(
            summary="Standard breakfast cereal with oats, nuts, and raisins.",
            added_sugars_and_sweeteners=SugarAnalysis(
                total_sugar_per_100g="18g",
                assessment="Moderate added sugar from honey and invert sugar syrup.",
            ),
            oils_and_fats=OilAnalysis(
                assessment="No palm oil or hydrogenated fats detected.",
            ),
            additives_and_preservatives=AdditiveAnalysis(
                assessment="Contains antioxidant tocopherols (INS 307b).",
            ),
            allergens=AllergenAnalysis(
                declared_allergens=["Oats", "Wheat", "Almonds"],
                assessment="Contains gluten and tree nuts.",
            ),
            fibre_and_whole_grains=FibreWholeGrainAnalysis(
                dietary_fibre_per_100g="7g",
                assessment="Good whole grain oat foundation.",
            ),
        ),
        research_status="completed",
        rankings=[],
        alternatives=[],
        sources=[],
    )

    with patch("app.main.analyze_product_image_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = mock_resp

        # Send exact multipart parameters emitted by frontend's api.js
        files = {"image": ("test_label.jpg", b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 50, "image/jpeg")}
        data = {
            "budget_inr": "",             # Empty string sent when budget is unset
            "priority": "best_value",      # Frontend default priority
            "pack_size_preference": "any", # Frontend pack size preference
            "avoid_ingredients": "[]",     # JSON array string
        }

        response = client.post("/api/products/analyze-image", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["original_product"]["name"] == "Muesli Fruit & Nut"
        assert res_json["original_product"]["brand"] == "Kellogg's"
