"""Automated unit and integration tests for Phase 3 product comparison, normalization, and ranking."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    NormalizedAlternative,
    NormalizedNutrition,
    OriginalProduct,
    RetailerListing,
)
from app.services.product_comparator import (
    calculate_price_per_100g,
    calculate_price_per_100ml,
    check_candidate_eligibility,
    deduplicate_and_merge_candidates,
    generate_recommendation_slots,
    normalize_serving_nutrition_to_100g,
    parse_price_in_inr,
    parse_weight_in_grams,
    score_alternative_candidate,
)


@pytest.fixture
def client():
    """Create a FastAPI test client instance."""
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# Unit Price & Deterministic Calculation Tests
# ==============================================================================

def test_calculate_price_per_100g():
    """Verify deterministic unit price calculation per 100 grams."""
    # 500g at ₹250 -> ₹50 per 100g
    assert calculate_price_per_100g(250.0, 500.0) == 50.0

    # 400g at ₹299 -> ₹74.75 per 100g
    assert calculate_price_per_100g(299.0, 400.0) == 74.75

    # Edge cases: 0 or negative
    assert calculate_price_per_100g(0.0, 500.0) is None
    assert calculate_price_per_100g(250.0, 0.0) is None
    assert calculate_price_per_100g(None, 500.0) is None
    assert calculate_price_per_100g(250.0, None) is None


def test_calculate_price_per_100ml_grams_vs_ml():
    """Verify grams and millilitres are treated with separate unit bases."""
    # 200ml at ₹80 -> ₹40 per 100ml
    assert calculate_price_per_100ml(80.0, 200.0) == 40.0
    assert calculate_price_per_100ml(None, 200.0) is None

    # Grams calculation does not interfere with ml
    cand_g = NormalizedAlternative(
        brand="BrandA",
        product_name="Cereal",
        pack_weight_g=500.0,
        unit_basis="g",
        listed_price_inr=200.0,
        price_per_100g=calculate_price_per_100g(200.0, 500.0),
    )
    assert cand_g.price_per_100g == 40.0
    assert cand_g.price_per_100ml is None


def test_parse_weight_in_grams():
    """Verify weight parsing for grams and kilograms."""
    assert parse_weight_in_grams("400g") == 400.0
    assert parse_weight_in_grams("400 gm") == 400.0
    assert parse_weight_in_grams("1 kg") == 1000.0
    assert parse_weight_in_grams("1.2 kgs") == 1200.0
    assert parse_weight_in_grams("750 grams") == 750.0
    assert parse_weight_in_grams("invalid text") is None


def test_parse_price_in_inr():
    """Verify INR price parsing from common Indian formatting."""
    assert parse_price_in_inr("₹ 299") == 299.0
    assert parse_price_in_inr("Rs. 350.50") == 350.50
    assert parse_price_in_inr("Rs 420") == 420.0
    assert parse_price_in_inr("INR 199") == 199.0
    assert parse_price_in_inr("Free") is None


def test_normalize_serving_nutrition_to_100g():
    """Verify serving-based nutrients are converted to 100g basis."""
    serving_nutri = NormalizedNutrition(
        serving_basis="per_serving",
        serving_size_g=40.0,
        energy_kcal=160.0,
        protein_g=4.0,       # 4g in 40g -> 10g in 100g
        fibre_g=3.2,         # 3.2g in 40g -> 8g in 100g
        total_sugar_g=2.4,   # 2.4g in 40g -> 6g in 100g
    )

    norm_100g = normalize_serving_nutrition_to_100g(serving_nutri, serving_size_g=40.0)
    assert norm_100g.serving_basis == "per_100g"
    assert norm_100g.protein_g == 10.0
    assert norm_100g.fibre_g == 8.0
    assert norm_100g.total_sugar_g == 6.0
    assert norm_100g.energy_kcal == 400.0


# ==============================================================================
# Eligibility & Hard Exclusions Tests
# ==============================================================================

def test_avoid_ingredients_hard_exclusion():
    """Ensure candidate containing avoid_ingredient is excluded."""
    cand = NormalizedAlternative(
        brand="BrandX",
        product_name="Crunchy Muesli",
        pack_weight_g=400.0,
        listed_price_inr=220.0,
        ingredient_list=["Rolled Oats", "Palmolein", "Sugar"],
    )

    status, reasons = check_candidate_eligibility(cand, avoid_ingredients=["palmolein"])
    assert status == "excluded"
    assert any("palmolein" in r for r in reasons)


def test_unknown_ingredient_safety_marked_uncertain():
    """Ensure missing ingredient list marks suitability as uncertain rather than safe."""
    cand = NormalizedAlternative(
        brand="BrandUnknown",
        product_name="Generic Muesli",
        pack_weight_g=400.0,
        listed_price_inr=199.0,
        ingredient_list=[],  # Missing ingredient data
    )

    status, reasons = check_candidate_eligibility(cand, avoid_ingredients=["palm oil"])
    assert status == "uncertain"
    assert any("unverified" in r.lower() for r in reasons)


def test_budget_hard_exclusion():
    """Ensure candidate exceeding specified budget is excluded."""
    cand = NormalizedAlternative(
        brand="PremiumBrand",
        product_name="Luxury Nut Muesli",
        pack_weight_g=500.0,
        listed_price_inr=450.0,
    )

    status, reasons = check_candidate_eligibility(cand, budget_inr=350.0)
    assert status == "excluded"
    assert any("exceeds specified budget" in r for r in reasons)


# ==============================================================================
# Deduplication & Merging Tests
# ==============================================================================

def test_deduplicate_and_merge_candidates():
    """Verify duplicate products from different sources merge listings and keep best price."""
    cand1 = NormalizedAlternative(
        brand="Kellogg's",
        product_name="Muesli Fruit Magic",
        pack_weight_g=500.0,
        listed_price_inr=320.0,
        retailer_listings=[
            RetailerListing(
                retailer_name="BigBasket",
                product_url="https://bigbasket.com/pd/1",
                listed_price_inr=320.0,
                retrieval_timestamp="2026-10-23T06:00:00Z",
            )
        ],
    )
    cand2 = NormalizedAlternative(
        brand="kellogg's",
        product_name="Muesli Fruit Magic",
        pack_weight_g=500.0,
        listed_price_inr=299.0,  # Lower price on Blinkit
        retailer_listings=[
            RetailerListing(
                retailer_name="Blinkit",
                product_url="https://blinkit.com/prn/1",
                listed_price_inr=299.0,
                retrieval_timestamp="2026-10-23T06:01:00Z",
            )
        ],
    )

    merged = deduplicate_and_merge_candidates([cand1, cand2])
    assert len(merged) == 1
    m = merged[0]
    assert m.listed_price_inr == 299.0
    assert m.price_per_100g == 59.80  # (299 / 500) * 100
    assert len(m.retailer_listings) == 2


# ==============================================================================
# Scoring & Priority Ranking Tests
# ==============================================================================

def test_lower_sugar_priority_scoring():
    """Verify candidate with lower sugar scores higher under lower_sugar priority."""
    cand_low_sugar = NormalizedAlternative(
        brand="BrandA",
        product_name="No Added Sugar Muesli",
        pack_weight_g=400.0,
        listed_price_inr=260.0,
        price_per_100g=65.0,
        nutrition_per_100g=NormalizedNutrition(
            protein_g=11.0, fibre_g=8.0, total_sugar_g=4.5, added_sugar_g=0.0
        ),
        ingredient_list=["Rolled Oats", "Almonds", "Seeds"],
    )

    cand_high_sugar = NormalizedAlternative(
        brand="BrandB",
        product_name="Honey Glazed Muesli",
        pack_weight_g=400.0,
        listed_price_inr=240.0,
        price_per_100g=60.0,
        nutrition_per_100g=NormalizedNutrition(
            protein_g=8.0, fibre_g=5.0, total_sugar_g=22.0, added_sugar_g=14.0
        ),
        ingredient_list=["Rolled Oats", "Sugar", "Honey Syrup"],
    )

    score_low = score_alternative_candidate(cand_low_sugar, priority="lower_sugar")
    score_high = score_alternative_candidate(cand_high_sugar, priority="lower_sugar")

    assert score_low.ingredient_nutrition_score > score_high.ingredient_nutrition_score
    assert score_low.total_score > score_high.total_score


def test_higher_fibre_priority_scoring():
    """Verify candidate with higher fibre scores higher under higher_fibre priority."""
    cand_high_fibre = NormalizedAlternative(
        brand="BrandHighFibre",
        product_name="Multi Seed & Oat Muesli",
        pack_weight_g=400.0,
        listed_price_inr=280.0,
        price_per_100g=70.0,
        nutrition_per_100g=NormalizedNutrition(protein_g=12.0, fibre_g=11.5, total_sugar_g=8.0),
        ingredient_list=["Rolled Oats 60%", "Chia Seeds", "Flax Seeds"],
    )

    cand_low_fibre = NormalizedAlternative(
        brand="BrandLowFibre",
        product_name="Corn & Rice Flakes Muesli",
        pack_weight_g=400.0,
        listed_price_inr=280.0,
        price_per_100g=70.0,
        nutrition_per_100g=NormalizedNutrition(protein_g=6.0, fibre_g=3.5, total_sugar_g=8.0),
        ingredient_list=["Corn Flakes", "Refined Flour"],
    )

    score_hf = score_alternative_candidate(cand_high_fibre, priority="higher_fibre")
    score_lf = score_alternative_candidate(cand_low_fibre, priority="higher_fibre")

    assert score_hf.ingredient_nutrition_score > score_lf.ingredient_nutrition_score


# ==============================================================================
# Recommendation Slots Generation Tests
# ==============================================================================

def test_generate_recommendation_slots():
    """Verify Best Overall Value, Cheapest Suitable, and Best Nutrition Match slots."""
    c_cheap = NormalizedAlternative(
        brand="Tata Soulfull",
        product_name="Muesli 400g",
        pack_weight_g=400.0,
        listed_price_inr=180.0,
        price_per_100g=45.0,  # Lowest unit price
        nutrition_per_100g=NormalizedNutrition(protein_g=9.0, fibre_g=7.0, total_sugar_g=9.0),
        suitability_status="suitable",
    )
    c_premium_nutri = NormalizedAlternative(
        brand="YogaBar",
        product_name="Super Muesli Dark Chocolate & Cranberry",
        pack_weight_g=400.0,
        listed_price_inr=299.0,
        price_per_100g=74.75,
        nutrition_per_100g=NormalizedNutrition(protein_g=16.0, fibre_g=10.0, total_sugar_g=6.0),  # Best nutrition
        suitability_status="suitable",
    )
    c_balanced = NormalizedAlternative(
        brand="Bagrry's",
        product_name="Muesli with Real Fruit",
        pack_weight_g=500.0,
        listed_price_inr=250.0,
        price_per_100g=50.0,  # Great balance of unit price and nutrition
        nutrition_per_100g=NormalizedNutrition(protein_g=12.0, fibre_g=8.5, total_sugar_g=7.5),
        suitability_status="suitable",
    )

    orig = OriginalProduct(brand="Kellogg's", product_name="Muesli", net_weight="400g")

    candidates = [
        score_alternative_candidate(c_cheap, original_product=orig),
        score_alternative_candidate(c_premium_nutri, original_product=orig),
        score_alternative_candidate(c_balanced, original_product=orig),
    ]

    recs = generate_recommendation_slots(candidates, original_product=orig)

    # 1. Cheapest Suitable must be Tata Soulfull (₹45/100g)
    assert recs.cheapest_suitable is not None
    assert recs.cheapest_suitable.product.brand == "Tata Soulfull"
    assert recs.cheapest_suitable.category == "cheapest_suitable"

    # 2. Best Nutrition Match must be YogaBar (16g protein, 10g fibre)
    assert recs.best_nutrition_match is not None
    assert recs.best_nutrition_match.product.brand == "YogaBar"
    assert recs.best_nutrition_match.category == "best_nutrition_match"

    # 3. Best Overall Value must be present
    assert recs.best_overall_value is not None
    assert recs.best_overall_value.category == "best_overall_value"

    assert recs.total_candidates_analyzed == 3
    assert recs.candidates_qualified == 3
    assert recs.candidates_excluded == 0


def test_recommendation_slots_empty_when_all_excluded():
    """Verify recommendation slots are None when all candidates are excluded."""
    excluded_cand = NormalizedAlternative(
        brand="BrandPalm",
        product_name="Palm Oil Muesli",
        pack_weight_g=400.0,
        listed_price_inr=200.0,
        price_per_100g=50.0,
        suitability_status="excluded",
        exclusion_reasons=["Contains palm oil"],
    )

    scored = [score_alternative_candidate(excluded_cand)]
    recs = generate_recommendation_slots(scored)

    assert recs.best_overall_value is None
    assert recs.cheapest_suitable is None
    assert recs.best_nutrition_match is None
    assert recs.candidates_excluded == 1
    assert recs.candidates_qualified == 0


# ==============================================================================
# Standalone Endpoint Integration Test (POST /api/products/compare)
# ==============================================================================

def test_api_products_compare_endpoint(client):
    """Verify POST /api/products/compare returns valid schema, deterministic rankings and recommendations."""
    payload = {
        "original_product": {
            "brand": "Kellogg's",
            "product_name": "Muesli Fruit Magic",
            "net_weight": "400g",
        },
        "candidates": [
            {
                "brand": "YogaBar",
                "product_name": "Super Muesli 400g",
                "pack_weight_g": 400.0,
                "unit_basis": "g",
                "listed_price_inr": 290.0,
                "ingredient_list": ["Rolled Oats", "Almonds", "Seeds"],
                "nutrition_per_100g": {
                    "protein_g": 14.0,
                    "fibre_g": 9.0,
                    "total_sugar_g": 8.0,
                },
                "retailer_listings": [
                    {
                        "retailer_name": "BigBasket",
                        "product_url": "https://bigbasket.com/pd/yogabar",
                        "listed_price_inr": 290.0,
                        "retrieval_timestamp": "2026-10-23T06:30:00Z",
                    }
                ],
            },
            {
                "brand": "Tata Soulfull",
                "product_name": "Muesli Crunch 400g",
                "pack_weight_g": 400.0,
                "unit_basis": "g",
                "listed_price_inr": 190.0,
                "ingredient_list": ["Millets", "Rolled Oats", "Palmolein"],
                "nutrition_per_100g": {
                    "protein_g": 9.0,
                    "fibre_g": 6.5,
                    "total_sugar_g": 11.0,
                },
                "retailer_listings": [
                    {
                        "retailer_name": "Blinkit",
                        "product_url": "https://blinkit.com/prn/tata",
                        "listed_price_inr": 190.0,
                        "retrieval_timestamp": "2026-10-23T06:30:00Z",
                    }
                ],
            },
        ],
        "budget_inr": 350.0,
        "priority": "balanced",
        "pack_size_preference": "similar",
        "avoid_ingredients": ["palmolein"],
    }

    response = client.post("/api/products/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "original_product" in data
    assert "rankings" in data
    assert "recommendations" in data
    assert "scoring_weights" in data

    # Verify scoring weights are transparent
    weights = data["scoring_weights"]
    assert weights["nutrition_ingredients"] == 0.45
    assert weights["price_value"] == 0.35
    assert weights["preference_fit"] == 0.20

    # Tata Soulfull contains palmolein, so it must be marked excluded
    rankings = data["rankings"]
    assert len(rankings) == 2

    tata_rank = next(r for r in rankings if r["candidate"]["brand"] == "Tata Soulfull")
    assert tata_rank["candidate"]["suitability_status"] == "excluded"

    yogabar_rank = next(r for r in rankings if r["candidate"]["brand"] == "YogaBar")
    assert yogabar_rank["candidate"]["suitability_status"] == "suitable"
    assert yogabar_rank["rank"] == 1

    # Recommendations: YogaBar is the qualified candidate
    recs = data["recommendations"]
    assert recs["candidates_qualified"] == 1
    assert recs["candidates_excluded"] == 1
    assert recs["best_overall_value"]["product"]["brand"] == "YogaBar"
    # Tata Soulfull was excluded due to palmolein, so cheapest suitable cannot be Tata Soulfull!
    assert recs["cheapest_suitable"]["product"]["brand"] == "YogaBar"
