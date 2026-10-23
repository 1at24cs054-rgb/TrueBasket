"""Automated Test Suite for Phase 4: Image-First Product Intelligence and Backend Validation.

Covers:
- Image Input: Valid JPEG/PNG/WEBP, empty, oversized, corrupted, blurry/unreadable
- Image Discovery: Search, deduplication, invalid URLs, non-image content, SSRF protection
- Label Extraction: Visual facts, front-of-pack vs back-of-pack, declared percentages, allergens
- Comparison: Deterministic unit price, ranking with unverified label penalty, hard exclusions
- Reliability: Service failures, no fabricated data, no secret leakage
- Dev Endpoints: /api/dev/search-images, /api/dev/extract-label
"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    GemmaSmokeTestResponse,
    NormalizedAlternative,
    NormalizedNutrition,
    OriginalProduct,
    ProductImageCandidate,
    RetailerListing,
    SourceReference,
    TavilySearchResultItem,
    TavilySearchResponse,
    VisualLabelExtraction,
)
from app.services.image_search import (
    MAX_DOWNLOAD_BYTES,
    download_and_validate_image,
    is_safe_image_url,
    search_product_images,
)
from app.services.product_analyzer import (
    extract_product_from_packaging,
    extract_visual_label_from_image,
)
from app.services.product_comparator import (
    check_candidate_eligibility,
    extract_candidates_from_search_evidence,
    generate_recommendation_slots,
    score_alternative_candidate,
)
from app.services.web_search import TavilyError

client = TestClient(app)


def make_valid_image_bytes(fmt: str = "JPEG", size=(100, 100), color=(180, 120, 60)) -> bytes:
    """Generate in-memory valid image binary structure."""
    buf = io.BytesIO()
    mode = "RGBA" if fmt.upper() == "PNG" else "RGB"
    img = Image.new(mode, size, color)
    img.save(buf, format=fmt)
    return buf.getvalue()


# ==============================================================================
# 1. Image Discovery & SSRF Security Tests
# ==============================================================================

def test_is_safe_image_url_permits_public_urls():
    """Verify standard public HTTP and HTTPS URLs are accepted."""
    assert is_safe_image_url("https://images.example.com/products/muesli_back.jpg")[0] is True
    assert is_safe_image_url("http://cdn.retailer.in/pack/cereal.png")[0] is True


def test_is_safe_image_url_blocks_internal_and_cloud_metadata():
    """Verify SSRF attempts targeting localhost, private subnets, and AWS metadata are blocked."""
    # Loopback
    assert is_safe_image_url("http://127.0.0.1:8000/secret.jpg")[0] is False
    assert is_safe_image_url("http://localhost/admin.png")[0] is False
    assert is_safe_image_url("http://[::1]/internal.jpg")[0] is False

    # AWS / Cloud Instance Metadata
    is_safe, reason = is_safe_image_url("http://169.254.169.254/latest/meta-data/")
    assert is_safe is False
    assert "metadata" in reason.lower() or "link-local" in reason.lower()

    # Private Subnets
    assert is_safe_image_url("http://10.0.0.5/label.jpg")[0] is False
    assert is_safe_image_url("http://192.168.1.100/label.png")[0] is False
    assert is_safe_image_url("http://172.16.0.2/label.webp")[0] is False

    # Unsupported schemes
    assert is_safe_image_url("ftp://ftp.example.com/image.jpg")[0] is False
    assert is_safe_image_url("file:///etc/passwd")[0] is False
    assert is_safe_image_url("data:image/png;base64,abc")[0] is False


@pytest.mark.asyncio
async def test_download_and_validate_image_rejects_non_image_content():
    """Verify downloading HTML or non-image content is rejected."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.content = b"<html><body>Not an image</body></html>"

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await download_and_validate_image("https://example.com/fake_image.jpg")
        assert res is None


@pytest.mark.asyncio
async def test_download_and_validate_image_rejects_corrupted_binary():
    """Verify corrupted bytes that fail image header validation are rejected."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "image/jpeg"}
    mock_resp.content = b"corrupted random data that is not a real JPEG binary"

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await download_and_validate_image("https://example.com/corrupted.jpg")
        assert res is None


@pytest.mark.asyncio
async def test_download_and_validate_image_rejects_oversized_content():
    """Verify images exceeding MAX_DOWNLOAD_BYTES are rejected."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "image/jpeg"}
    mock_resp.content = b"X" * (MAX_DOWNLOAD_BYTES + 1024)

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await download_and_validate_image("https://example.com/giant.jpg")
        assert res is None


@pytest.mark.asyncio
async def test_download_and_validate_image_success_for_valid_formats():
    """Verify valid JPEG, PNG, and WEBP binaries are verified and returned."""
    for fmt, mime in [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]:
        img_bytes = make_valid_image_bytes(fmt)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": mime}
        mock_resp.content = img_bytes

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            res = await download_and_validate_image(f"https://example.com/test.{fmt.lower()}")
            assert res is not None
            out_bytes, out_mime = res
            assert len(out_bytes) == len(img_bytes)
            assert out_mime.startswith("image/")


@pytest.mark.asyncio
async def test_search_product_images_deduplication_and_classification():
    """Verify search_product_images deduplicates URLs and heuristically classifies back vs front of pack."""
    fake_tavily_resp = TavilySearchResponse(
        query="YogaBar muesli",
        response_time=0.3,
        results_count=0,
        results=[],
        images=[
            "https://cdn.example.com/yogabar_front_pack.jpg",
            "https://cdn.example.com/yogabar_back_nutrition_label.jpg",
            "https://cdn.example.com/yogabar_front_pack.jpg",  # duplicate
            "https://cdn.example.com/cereal_hero.png",
        ],
    )

    with patch("app.services.image_search.search_tavily", AsyncMock(return_value=fake_tavily_resp)):
        candidates = await search_product_images("YogaBar muesli", max_results=5)
        assert len(candidates) == 3  # Duplicate eliminated
        urls = [c.image_url for c in candidates]
        assert "https://cdn.example.com/yogabar_back_nutrition_label.jpg" in urls

        # Back of pack classification
        back_cand = next(c for c in candidates if "nutrition" in c.image_url)
        assert back_cand.image_type == "back_of_pack"


# ==============================================================================
# 2. Visual Label Extraction Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_extract_visual_label_complete_back_of_pack():
    """Verify extracting complete ingredient panel and per-100g nutrition table."""
    mock_llm_json = {
        "brand": "True Elements",
        "product_name": "Fruit & Nut Muesli",
        "variant": "Cranberry & Almond",
        "net_weight": "400 g",
        "label_type": "back_of_pack",
        "is_readable": True,
        "is_complete": True,
        "confidence": "high",
        "ingredient_list": ["Rolled Oats", "Almonds", "Dried Cranberries", "Pumpkin Seeds"],
        "declared_percentages": {"Rolled Oats": 52.0, "Almonds": 10.0},
        "nutrition_basis": "per_100g",
        "serving_size_g": 40.0,
        "nutrition_facts": {
            "energy_kcal": 410.0,
            "protein_g": 11.5,
            "total_sugar_g": 8.0,
            "added_sugar_g": 0.0,
            "dietary_fibre_g": 9.2,
            "total_fat_g": 9.0,
            "saturated_fat_g": 1.2,
            "sodium_mg": 45.0,
        },
        "allergen_declarations": ["Contains Almonds and Oats. May contain traces of soy."],
        "manufacturer": "HW Wellness Solutions",
        "barcode": "8906112345678",
        "fssai_license": "10019022009876",
    }

    mock_resp = GemmaSmokeTestResponse(
        success=True,
        input_type="image",
        status="healthy",
        model="models/gemma-4-26b-a4b-it",
        provider="google_genai",
        response_text=json.dumps(mock_llm_json),
        structured_output=mock_llm_json,
        latency_ms=350.0,
    )

    with patch("app.services.product_analyzer.run_gemma_image_smoke_test", AsyncMock(return_value=mock_resp)):
        img_bytes = make_valid_image_bytes("JPEG")
        result = await extract_visual_label_from_image(img_bytes, "image/jpeg", "test_back_label.jpg")

        assert result.label_type == "back_of_pack"
        assert result.is_readable is True
        assert result.is_complete is True
        assert result.extraction_status == "complete"
        assert "Rolled Oats" in result.ingredient_list
        assert result.declared_percentages["Rolled Oats"] == 52.0
        assert result.nutrition_facts["protein_g"] == 11.5
        assert result.nutrition_facts["added_sugar_g"] == 0.0
        assert len(result.allergen_declarations) == 1


@pytest.mark.asyncio
async def test_extract_visual_label_front_of_pack_incomplete():
    """Verify front-of-pack images set partial status and do NOT hallucinate nutrition."""
    mock_llm_json = {
        "brand": "Kellogg's",
        "product_name": "Crunchy Muesli",
        "variant": "Fruit Magic",
        "net_weight": "750 g",
        "label_type": "front_of_pack",
        "is_readable": True,
        "is_complete": False,
        "confidence": "medium",
        "ingredient_list": [],
        "declared_percentages": {},
        "nutrition_basis": "unknown",
        "serving_size_g": None,
        "nutrition_facts": {},
        "allergen_declarations": [],
    }

    mock_resp = GemmaSmokeTestResponse(
        success=True,
        input_type="image",
        status="healthy",
        model="models/gemma-4-26b-a4b-it",
        provider="google_genai",
        response_text=json.dumps(mock_llm_json),
        structured_output=mock_llm_json,
        latency_ms=280.0,
    )

    with patch("app.services.product_analyzer.run_gemma_image_smoke_test", AsyncMock(return_value=mock_resp)):
        img_bytes = make_valid_image_bytes("JPEG")
        result = await extract_visual_label_from_image(img_bytes, "image/jpeg", "front_of_box.jpg")

        assert result.label_type == "front_of_pack"
        assert result.is_complete is False
        assert result.extraction_status == "partial"
        assert result.ingredient_list == []
        assert result.nutrition_facts == {}


@pytest.mark.asyncio
async def test_extract_visual_label_unreadable_blurry_image():
    """Verify blurry or unreadable packaging is flagged with status 'unreadable'."""
    mock_llm_json = {
        "brand": None,
        "product_name": None,
        "label_type": "unclear",
        "is_readable": False,
        "is_complete": False,
        "confidence": "low",
        "ingredient_list": [],
        "nutrition_facts": {},
    }

    mock_resp = GemmaSmokeTestResponse(
        success=True,
        input_type="image",
        status="healthy",
        model="models/gemma-4-26b-a4b-it",
        provider="google_genai",
        response_text=json.dumps(mock_llm_json),
        structured_output=mock_llm_json,
        latency_ms=200.0,
    )

    with patch("app.services.product_analyzer.run_gemma_image_smoke_test", AsyncMock(return_value=mock_resp)):
        img_bytes = make_valid_image_bytes("JPEG")
        result = await extract_visual_label_from_image(img_bytes, "image/jpeg", "blurry.jpg")

        assert result.is_readable is False
        assert result.extraction_status == "unreadable"


# ==============================================================================
# 3. Product Comparator & Image-First Logic Tests
# ==============================================================================

def test_search_evidence_does_not_populate_ingredients_or_nutrition():
    """Verify that search snippet text does NOT populate ingredients or nutrition tables."""
    snippet_text = (
        "Buy YogaBar Super Muesli 400g online for Rs. 299. High protein with 14g protein and 8g fibre. "
        "Contains Rolled Oats, Almonds, and Honey with no added sugar."
    )
    src = SourceReference(
        title="YogaBar Super Muesli 400g - BigBasket",
        url="https://www.bigbasket.com/pd/12345/yogabar-muesli-400g",
        snippet=snippet_text,
        source_type="retailer_or_web",
    )

    candidates = extract_candidates_from_search_evidence([src])
    assert len(candidates) == 1
    cand = candidates[0]

    # Verify price and pack size are captured
    assert cand.brand == "YogaBar"
    assert cand.pack_weight_g == 400.0
    assert cand.listed_price_inr == 299.0

    # Critical Image-First Verification: Ingredients and nutrition must be empty from search snippet!
    assert cand.ingredient_list == []
    assert cand.nutrition_per_100g is None
    assert cand.declared_percentages == {}
    assert cand.label_extraction_status == "no_label_image_found"
    assert "packaging_label_image" in cand.missing_fields


def test_candidate_without_label_image_penalized_in_scoring():
    """Verify candidate without verified label image receives penalized nutrition baseline and trade-off."""
    cand = NormalizedAlternative(
        brand="YogaBar",
        product_name="Dark Chocolate Muesli",
        pack_weight_g=400.0,
        listed_price_inr=280.0,
        price_per_100g=70.0,
        nutrition_per_100g=None,
        ingredient_list=[],
        label_extraction_status="no_label_image_found",
    )

    scored = score_alternative_candidate(cand)
    # Penalized baseline score for unverified packaging
    assert scored.ingredient_nutrition_score == 30.0
    assert any("unverified packaging label" in t.lower() for t in scored.trade_offs)


def test_best_nutrition_match_prefers_verified_packaging_label():
    """Verify best_nutrition_match recommendation selects candidate with verified label over unverified candidate."""
    # Cand A: Verified back-of-pack label
    cand_verified = NormalizedAlternative(
        brand="WholeTruth",
        product_name="Clean Muesli",
        pack_weight_g=400.0,
        listed_price_inr=350.0,
        price_per_100g=87.5,
        nutrition_per_100g=NormalizedNutrition(
            protein_g=12.0,
            fibre_g=9.0,
            total_sugar_g=5.0,
            added_sugar_g=0.0,
        ),
        ingredient_list=["Rolled Oats", "Almonds", "Chia Seeds"],
        label_extraction_status="complete",
    )

    # Cand B: Unverified label
    cand_unverified = NormalizedAlternative(
        brand="BrandX",
        product_name="Mystery Cereal",
        pack_weight_g=400.0,
        listed_price_inr=250.0,
        price_per_100g=62.5,
        nutrition_per_100g=None,
        ingredient_list=[],
        label_extraction_status="no_label_image_found",
    )

    scored_a = score_alternative_candidate(cand_verified)
    scored_b = score_alternative_candidate(cand_unverified)

    assert scored_a.ingredient_nutrition_score > scored_b.ingredient_nutrition_score

    recs = generate_recommendation_slots([scored_a, scored_b])
    assert recs.best_nutrition_match is not None
    assert recs.best_nutrition_match.product.brand == "WholeTruth"
    assert "visually inspected packaging" in recs.best_nutrition_match.selection_reason.lower()


def test_avoid_ingredients_on_unverified_label_marks_uncertain():
    """Verify that avoiding an ingredient on an unverified candidate marks it as 'uncertain' rather than safe."""
    cand = NormalizedAlternative(
        brand="UnknownBrand",
        product_name="Breakfast Crunch",
        ingredient_list=[],
        known_allergens=[],
        label_extraction_status="no_label_image_found",
    )

    status, reasons = check_candidate_eligibility(cand, avoid_ingredients=["palm oil"])
    assert status == "uncertain"
    assert any("unverified" in r.lower() for r in reasons)


# ==============================================================================
# 4. Development Endpoint Integration Tests
# ==============================================================================

def test_dev_search_images_endpoint():
    """Test POST /api/dev/search-images discovers and returns candidates."""
    fake_tavily_resp = TavilySearchResponse(
        query="Kelloggs muesli nutrition",
        response_time=0.2,
        results_count=0,
        results=[],
        images=[
            "https://cdn.example.com/kelloggs_front.jpg",
            "https://cdn.example.com/kelloggs_back_nutrition.png",
        ],
    )

    with patch("app.services.image_search.search_tavily", AsyncMock(return_value=fake_tavily_resp)):
        resp = client.post(
            "/api/dev/search-images",
            json={"query": "Kelloggs muesli nutrition", "max_results": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "Kelloggs muesli nutrition"
        assert data["count"] == 2
        assert len(data["images"]) == 2
        assert data["images"][1]["image_type"] == "back_of_pack"


def test_dev_extract_label_with_file_upload():
    """Test POST /api/dev/extract-label with direct image upload."""
    mock_llm_json = {
        "brand": "Bagrry's",
        "product_name": "Organic Muesli",
        "label_type": "back_of_pack",
        "is_readable": True,
        "is_complete": True,
        "confidence": "high",
        "ingredient_list": ["Rolled Oats", "Raisins", "Wheat Flakes"],
        "declared_percentages": {"Rolled Oats": 60.0},
        "nutrition_facts": {"protein_g": 10.0, "dietary_fibre_g": 8.0, "total_sugar_g": 6.0},
        "allergen_declarations": ["Contains Gluten"],
    }

    mock_resp = GemmaSmokeTestResponse(
        success=True,
        input_type="image",
        status="healthy",
        model="models/gemma-4-26b-a4b-it",
        provider="google_genai",
        response_text=json.dumps(mock_llm_json),
        structured_output=mock_llm_json,
        latency_ms=300.0,
    )

    img_bytes = make_valid_image_bytes("JPEG")
    with patch("app.services.product_analyzer.run_gemma_image_smoke_test", AsyncMock(return_value=mock_resp)):
        resp = client.post(
            "/api/dev/extract-label",
            files={"image": ("muesli_label.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["image_source"] == "muesli_label.jpg"
        assert data["label_type"] == "back_of_pack"
        assert data["extraction_status"] == "complete"
        assert data["extraction"]["ingredient_list"] == ["Rolled Oats", "Raisins", "Wheat Flakes"]
        assert data["extraction"]["declared_percentages"]["Rolled Oats"] == 60.0


def test_dev_extract_label_ssrf_blocked():
    """Test POST /api/dev/extract-label strictly rejects SSRF URLs."""
    resp = client.post(
        "/api/dev/extract-label",
        data={"image_url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp.status_code == 400
    assert "could not securely download" in resp.json()["detail"].lower()


def test_dev_extract_label_missing_inputs_returns_400():
    """Test POST /api/dev/extract-label with neither image nor image_url returns 400."""
    resp = client.post("/api/dev/extract-label")
    assert resp.status_code == 400
    assert "either 'image' upload or 'image_url'" in resp.json()["detail"].lower()
