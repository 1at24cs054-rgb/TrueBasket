"""Automated unit and integration tests for Phase 2 product image analysis."""

import io
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas import OriginalProduct, SourceReference
from app.services.product_analyzer import (
    _classify_source_type,
    extract_product_from_packaging,
    synthesize_ingredient_intelligence,
)
from app.services.web_search import TavilyError


@pytest.fixture
def client():
    """Create a FastAPI test client instance."""
    with TestClient(app) as test_client:
        yield test_client


def _create_test_image(format="JPEG", size=(200, 200), color=(255, 255, 255)) -> bytes:
    """Generate in-memory test image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


# ==============================================================================
# Endpoint Validation Tests
# ==============================================================================

def test_analyze_image_invalid_mime_type(client):
    """Ensure non-image uploads return HTTP 400."""
    response = client.post(
        "/api/products/analyze-image",
        files={"image": ("test.txt", b"plain text content", "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_analyze_image_empty_file(client):
    """Ensure empty file uploads return HTTP 400."""
    response = client.post(
        "/api/products/analyze-image",
        files={"image": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_analyze_image_file_too_large(client):
    """Ensure files exceeding 10MB return HTTP 413."""
    large_payload = b"0" * (10 * 1024 * 1024 + 100)
    response = client.post(
        "/api/products/analyze-image",
        files={"image": ("large.jpg", large_payload, "image/jpeg")},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"].lower()


def test_analyze_image_invalid_priority(client):
    """Ensure invalid priority value returns HTTP 400."""
    img_bytes = _create_test_image()
    response = client.post(
        "/api/products/analyze-image",
        files={"image": ("sample.jpg", img_bytes, "image/jpeg")},
        data={"priority": "invalid_priority"},
    )
    assert response.status_code == 400
    assert "Invalid priority" in response.json()["detail"]


def test_analyze_image_invalid_pack_size_preference(client):
    """Ensure invalid pack_size_preference returns HTTP 400."""
    img_bytes = _create_test_image()
    response = client.post(
        "/api/products/analyze-image",
        files={"image": ("sample.jpg", img_bytes, "image/jpeg")},
        data={"pack_size_preference": "invalid_pref"},
    )
    assert response.status_code == 400
    assert "Invalid pack_size_preference" in response.json()["detail"]


def test_analyze_image_invalid_avoid_ingredients_json(client):
    """Ensure malformed JSON in avoid_ingredients returns HTTP 400."""
    img_bytes = _create_test_image()
    response = client.post(
        "/api/products/analyze-image",
        files={"image": ("sample.jpg", img_bytes, "image/jpeg")},
        data={"avoid_ingredients": "[[malformed json"},
    )
    assert response.status_code == 400
    assert "Invalid JSON format" in response.json()["detail"]


# ==============================================================================
# End-to-End Analysis Pipeline Mock Tests
# ==============================================================================

def test_analyze_image_successful_pipeline(client):
    """Verify complete end-to-end endpoint with mocked AI and search."""
    img_bytes = _create_test_image()

    fake_extracted_product = OriginalProduct(
        brand="YogaBar",
        product_name="Super Muesli",
        variant="Fruits, Nuts & Seeds",
        net_weight="400g",
        serving_size="40g",
        ingredient_list=[
            "Rolled Oats (50%)",
            "Almonds (12%)",
            "Raisins (8%)",
            "Chia Seeds",
            "Edible Vegetable Oil (Palmolein)",
            "INS 322",
        ],
        declared_percentages={"Rolled Oats": 50.0, "Almonds": 12.0, "Raisins": 8.0},
        nutrition_facts={
            "energy_kcal": 410.0,
            "protein_g": 12.5,
            "total_sugar_g": 9.2,
            "added_sugar_g": 2.0,
            "dietary_fibre_g": 8.5,
            "total_fat_g": 11.0,
        },
        allergen_warnings=["Contains Almonds and Gluten"],
        panel_type="nutrition_and_ingredients",
        ingredient_panel_missing=False,
    )

    fake_sources = [
        SourceReference(
            title="YogaBar Super Muesli 400g - BigBasket",
            url="https://www.bigbasket.com/pd/12345/yogabar-muesli",
            snippet="High protein muesli with 50% oats, almonds and seeds.",
            source_type="retailer_or_web",
            score=0.92,
        ),
        SourceReference(
            title="FSSAI Guidelines on Cereal Labeling",
            url="https://www.fssai.gov.in/standards",
            snippet="Standard labeling regulations for packaged breakfast foods in India.",
            source_type="food_safety_regulator",
            score=0.85,
        ),
    ]

    with patch(
        "app.services.product_analyzer.extract_product_from_packaging",
        new_callable=AsyncMock,
    ) as mock_extract, patch(
        "app.services.product_analyzer.research_product_online",
        new_callable=AsyncMock,
    ) as mock_research:
        mock_extract.return_value = fake_extracted_product
        mock_research.return_value = fake_sources

        response = client.post(
            "/api/products/analyze-image",
            files={"image": ("muesli.jpg", img_bytes, "image/jpeg")},
            data={
                "priority": "higher_fibre",
                "avoid_ingredients": '["palmolein", "sugar"]',
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 1. Original Product Validation
        prod = data["original_product"]
        assert prod["brand"] == "YogaBar"
        assert prod["product_name"] == "Super Muesli"
        assert prod["declared_percentages"]["Rolled Oats"] == 50.0

        # 2. Ingredient Analysis Validation
        analysis = data["ingredient_analysis"]
        assert "findings" in analysis
        assert len(analysis["findings"]) > 0

        # Verify fact vs interpretation distinction
        statuses = [f["status"] for f in analysis["findings"]]
        assert "verified_fact" in statuses

        # Check palm oil flag
        assert analysis["oils_and_fats"]["has_palm_oil"] is True

        # Check avoided ingredients flag
        flags = analysis["flags_for_user_avoid_list"]
        assert len(flags) > 0
        avoided_terms = [f["avoided_term"] for f in flags]
        assert "palmolein" in avoided_terms

        # 3. Sources & Research Status
        assert len(data["sources"]) == 2
        assert data["research_status"] == "complete"
        assert data["rankings"] == []
        assert data["alternatives"] == []


def test_analyze_image_missing_ingredient_panel_handling(client):
    """Verify handling when the image is only the front of the pack."""
    img_bytes = _create_test_image()

    front_only_product = OriginalProduct(
        brand="Kellogg's",
        product_name="Muesli with 21% Fruit and Nut",
        panel_type="front_of_pack",
        ingredient_panel_missing=True,
        ingredient_list=[],
    )

    with patch(
        "app.services.product_analyzer.extract_product_from_packaging",
        new_callable=AsyncMock,
    ) as mock_extract, patch(
        "app.services.product_analyzer.research_product_online",
        new_callable=AsyncMock,
    ) as mock_research:
        mock_extract.return_value = front_only_product
        mock_research.return_value = []

        response = client.post(
            "/api/products/analyze-image",
            files={"image": ("front.jpg", img_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()

        # Check missing information reports panel absence
        missing = data["missing_information"]
        assert any("front packaging" in m.lower() for m in missing)
        assert data["research_status"] == "partial"


def test_analyze_image_search_failure_graceful_fallback(client):
    """Ensure search engine failures fall back gracefully to label-only analysis."""
    img_bytes = _create_test_image()

    label_product = OriginalProduct(
        brand="Bagrry's",
        product_name="Crunchy Muesli",
        ingredient_list=["Rolled Oats (45%)", "Wheat Flakes", "Raisins"],
        panel_type="back_of_pack",
        ingredient_panel_missing=False,
    )

    with patch(
        "app.services.product_analyzer.extract_product_from_packaging",
        new_callable=AsyncMock,
    ) as mock_extract, patch(
        "app.services.product_analyzer.search_tavily",
        side_effect=TavilyError("Search service timeout"),
    ):
        mock_extract.return_value = label_product

        response = client.post(
            "/api/products/analyze-image",
            files={"image": ("muesli.jpg", img_bytes, "image/jpeg")},
        )

        # Must not crash, returns 200 with label analysis
        assert response.status_code == 200
        data = response.json()
        assert data["original_product"]["brand"] == "Bagrry's"
        assert len(data["sources"]) == 0
        assert data["research_status"] == "complete"


# ==============================================================================
# Helper Unit Tests
# ==============================================================================

def test_source_classification():
    """Verify URL classifier categorizes official, regulator, and retailer sources."""
    # Regulator
    assert _classify_source_type("https://www.fssai.gov.in/advisories", "Kellogg's") == "food_safety_regulator"
    assert _classify_source_type("https://consumeraffairs.nic.in/standards", None) == "food_safety_regulator"

    # Official manufacturer
    assert _classify_source_type("https://yogabar.in/products/muesli", "YogaBar") == "official_manufacturer"
    assert _classify_source_type("https://www.kelloggs.in/products/muesli", "Kellogg's") == "official_manufacturer"

    # Retailer / Web
    assert _classify_source_type("https://www.bigbasket.com/pd/123", "Bagrrys") == "retailer_or_web"
    assert _classify_source_type("https://blinkit.com/prn/muesli", "TrueBasket") == "retailer_or_web"
