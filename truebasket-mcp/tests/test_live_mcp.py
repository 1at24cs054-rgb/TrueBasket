"""Live integration tests for TrueBasket MCP Server against the running backend.

Verifies end-to-end communication, live Open Food Facts proxy,
live price discovery, and live image analysis through the MCP tools.
"""

import base64
import os
import pytest
from pathlib import Path

from server import (
    search_products,
    get_product_details,
    compare_alternatives,
    find_product_prices,
    check_ingredient_preferences,
    analyze_food_image,
)


@pytest.mark.asyncio
async def test_live_search_products_muesli():
    """Live test: search for muesli returns real Open Food Facts products."""
    result = await search_products(query="muesli", page_size=5)
    assert "error" not in result
    assert result["total_matches"] > 0
    assert len(result["products"]) > 0

    first_product = result["products"][0]
    assert "product_name" in first_product
    assert "brand" in first_product
    assert "code" in first_product


@pytest.mark.asyncio
async def test_live_get_product_details_true_elements():
    """Live test: fetch real product details for True Elements Muesli (8906112662803)."""
    barcode = "8906112662803"
    result = await get_product_details(barcode=barcode)
    assert result["found"] is True
    assert result["barcode"] == barcode
    assert "True Elements" in (result.get("brand") or "") or "Muesli" in (result.get("product_name") or "")
    assert len(result["ingredients"]) > 0
    assert result["nutrition_per_100g"]["protein_g"] is not None
    assert result["nutrition_per_100g"]["sugars_g"] is not None


@pytest.mark.asyncio
async def test_live_compare_alternatives():
    """Live test: compare alternatives for real muesli product."""
    barcode = "8906112662803"
    result = await compare_alternatives(
        product_identifier=barcode,
        excluded_ingredients=["palm oil"],
        priority="higher_fibre",
    )
    assert "error" not in result
    assert result["alternatives_count"] > 0
    assert len(result["recommended_alternatives"]) > 0

    alt = result["recommended_alternatives"][0]
    assert "product_name" in alt
    assert "badge" in alt
    assert "reason" in alt


@pytest.mark.asyncio
async def test_live_find_product_prices():
    """Live test: fetch real prices from live prices endpoint."""
    result = await find_product_prices(product_name="Kelloggs Muesli")
    assert "error" not in result
    assert "listings" in result
    # If live prices returned listings, verify structure
    if result["listings_count"] > 0:
        listing = result["listings"][0]
        assert "retailer" in listing
        assert "price_inr" in listing


@pytest.mark.asyncio
async def test_live_check_ingredient_preferences_barcode():
    """Live test: check preferences by looking up barcode on live backend."""
    barcode = "8906112662803"
    result = await check_ingredient_preferences(
        product_identifier=barcode,
        excluded_ingredients=["palm oil", "artificial sweeteners"],
    )
    assert result["status"] in ("CLEAR", "VIOLATION_DETECTED")
    assert result["total_ingredients_audited"] > 0
    assert "disclaimer" in result


@pytest.mark.asyncio
async def test_live_analyze_food_image_local():
    """Live test: analyze local package photo using MCP analyze_food_image tool."""
    img_path = Path(__file__).resolve().parent.parent.parent / "truebasket-backend" / "test_package.jpg"
    if not img_path.exists():
        pytest.skip(f"Test image not found at {img_path}")

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    b64_img = base64.b64encode(img_bytes).decode()
    result = await analyze_food_image(image_base64=b64_img, priority="best_value")

    assert "error" not in result
    assert "identified_product" in result
    identified = result["identified_product"]
    assert identified.get("brand") or identified.get("product_name")
