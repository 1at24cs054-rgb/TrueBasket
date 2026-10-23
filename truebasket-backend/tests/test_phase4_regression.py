"""Regression tests reproducing Phase 4 live validation failure modes.

Specifically tests:
1. Unidentifiable input (null brand & name) returns explicit failed status and HTTP 422.
2. Phase 4 failure reproduction: 0 usable labels, 0 nutrition panels, 1 candidate with verified price,
   and avoid-ingredient constraints.
   Ensures recommendations do NOT select the same unverified candidate for all 3 slots,
   marks cheapest_suitable=None, and marks best_nutrition_match=None.
3. Candidate images rejected for low resolution or missing label panel facts.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    NormalizedAlternative,
    OriginalProduct,
    ProductImageCandidate,
    RetailerListing,
    VisualLabelExtraction,
)
from app.services.image_search import download_and_validate_image_detailed
from app.services.product_comparator import (
    check_candidate_eligibility,
    generate_recommendation_slots,
    score_alternative_candidate,
)


def _make_test_image(width: int = 400, height: int = 400) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color="white")
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_unidentifiable_product_returns_422_with_failed_status():
    """When an uploaded image does not contain identifiable brand/product_name,
    API must return HTTP 422 with research_status='failed', recommendations=None,
    and clear warnings rather than pretending analysis succeeded.
    """
    client = TestClient(app)
    img_bytes = _make_test_image()

    unidentified_product = OriginalProduct(
        brand=None,
        product_name=None,
        variant=None,
        net_weight=None,
        panel_type="unclear",
        ingredient_panel_missing=True,
        ingredient_list=[],
        visual_extraction=VisualLabelExtraction(
            image_url_or_ref="user_uploaded_image",
            label_type="unclear",
            is_readable=False,
            is_complete=False,
            extraction_status="unreadable",
        ),
    )

    with patch(
        "app.services.product_analyzer.extract_product_from_packaging",
        new_callable=AsyncMock,
    ) as mock_extract:
        mock_extract.return_value = unidentified_product

        response = client.post(
            "/api/products/analyze-image",
            files={"image": ("unidentified.jpg", img_bytes, "image/jpeg")},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["research_status"] == "failed"
        assert data["original_product"]["brand"] is None
        assert data["original_product"]["product_name"] is None
        assert data["recommendations"] is None
        assert data["alternatives"] == []
        assert data["rankings"] == []
        assert any("could not be identified" in m.lower() for m in data["missing_information"])
        assert any("identification failed" in w.lower() for w in data["warnings"])


def test_phase4_failure_reproduction_unsupported_recommendations():
    """Reproduce Phase 4 live report:
    - 0 usable labels
    - 0 readable nutrition panels
    - 1 candidate with a verifiable price
    - User specified avoid_ingredients=['artificial sweetener']

    Expected:
    - cheapest_suitable MUST be None (unverified candidate cannot be confirmed safe)
    - best_nutrition_match MUST be None (no verified nutrition data)
    - best_overall_value selects the single candidate with price, but labels it unverified
    - NOT all three recommendation slots select the same candidate!
    """
    # Cand 1: Has price Rs. 300 (400g -> Rs. 75/100g), but unverified label
    listing1 = RetailerListing(
        retailer_name="BigBasket",
        product_url="https://bigbasket.com/cand1",
        pack_size_raw="400g",
        listed_price_inr=300.0,
        retrieval_timestamp="2026-10-23T00:00:00Z",
    )
    cand1 = NormalizedAlternative(
        brand="YogaBar",
        product_name="Muesli A",
        pack_weight_g=400.0,
        listed_price_inr=300.0,
        price_per_100g=75.0,
        label_extraction_status="no_label_image_found",
        ingredient_list=[],
        nutrition_per_100g=None,
        retailer_listings=[listing1],
        price_retrieval_timestamp="2026-10-23T00:00:00Z",
        missing_fields=["packaging_label_image"],
    )

    # Cand 2: No verified price, unverified label
    cand2 = NormalizedAlternative(
        brand="Bagrry's",
        product_name="Muesli B",
        pack_weight_g=400.0,
        listed_price_inr=None,
        price_per_100g=None,
        label_extraction_status="no_label_image_found",
        ingredient_list=[],
        nutrition_per_100g=None,
        retailer_listings=[],
        price_retrieval_timestamp="2026-10-23T00:00:00Z",
        missing_fields=["pricing", "packaging_label_image"],
    )

    # Check eligibility with avoid_ingredients constraint
    avoid_list = ["artificial sweetener"]
    for c in [cand1, cand2]:
        status, reasons = check_candidate_eligibility(c, avoid_ingredients=avoid_list)
        c.suitability_status = status  # Will be 'uncertain' because ingredients are unverified
        c.exclusion_reasons = reasons

    assert cand1.suitability_status == "uncertain"
    assert cand2.suitability_status == "uncertain"

    # Score candidates
    sc1 = score_alternative_candidate(cand1, priority="balanced")
    sc2 = score_alternative_candidate(cand2, priority="balanced")

    # Generate recommendation slots
    recs = generate_recommendation_slots(
        scored_candidates=[sc1, sc2],
        avoid_ingredients=avoid_list,
        priority="balanced",
    )

    # 1. Best overall value should be cand1 (price comparison available)
    assert recs.best_overall_value is not None
    assert recs.best_overall_value.product.brand == "YogaBar"
    assert any("unverified" in info.lower() for info in recs.best_overall_value.missing_or_uncertain_info)

    # 2. Cheapest suitable MUST be None because cand1 cannot be verified safe for artificial sweetener
    assert recs.cheapest_suitable is None

    # 3. Best nutrition match MUST be None because 0 candidates have verified nutrition data
    assert recs.best_nutrition_match is None

    # 4. Verified: All three slots do NOT select the same candidate!
    slots_with_cand1 = [
        s for s in [recs.best_overall_value, recs.cheapest_suitable, recs.best_nutrition_match]
        if s is not None and s.product.brand == "YogaBar"
    ]
    assert len(slots_with_cand1) == 1


@pytest.mark.asyncio
async def test_download_and_validate_image_detailed_low_resolution():
    """Verify image below 200px threshold is rejected with low_resolution reason."""
    small_bytes = _make_test_image(width=150, height=180)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_resp.content = small_bytes
        mock_get.return_value = mock_resp

        content, mime, reason = await download_and_validate_image_detailed(
            "https://example.com/tiny_thumb.jpg",
            min_dimension_px=200,
        )

        assert content is None
        assert mime is None
        assert reason is not None
        assert "low_resolution_150x180" in reason
