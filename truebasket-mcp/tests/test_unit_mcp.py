"""Unit tests for TrueBasket MCP Server tools and security boundaries.

Tests MCP tool registration, input validation, mocked backend responses,
SSRF defense, and secret redaction.
"""

import base64
import io
import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

import server
from server import (
    mcp_app,
    search_products,
    get_product_details,
    analyze_food_image,
    compare_alternatives,
    find_product_prices,
    check_ingredient_preferences,
    is_private_ip,
    validate_and_fetch_url,
    decode_base64_image,
    redact_secrets,
)


# ==============================================================================
# 1. Server Startup & Tool Registration Tests
# ==============================================================================

def test_server_metadata_and_tool_registration():
    """Verify MCP server name and registered tools."""
    assert mcp_app.name == "TrueBasket"
    registered_tools = mcp_app._tool_manager.list_tools()
    tool_names = [t.name for t in registered_tools]

    expected_tools = [
        "search_products",
        "get_product_details",
        "analyze_food_image",
        "compare_alternatives",
        "find_product_prices",
        "check_ingredient_preferences",
    ]
    for expected in expected_tools:
        assert expected in tool_names, f"Tool '{expected}' is missing from MCP server registration."


# ==============================================================================
# 2. Secret Redaction Tests
# ==============================================================================

def test_secret_redaction():
    """Ensure API keys and bearer tokens are never leaked in error logs."""
    raw_text = "Error connecting with sk-or-v1-abcdef1234567890abcdef and tvly-xyz1234567890, Bearer secret_token_12345678"
    redacted = redact_secrets(raw_text)
    assert "sk-or-v1-abcdef1234567890abcdef" not in redacted
    assert "tvly-xyz1234567890" not in redacted
    assert "secret_token_12345678" not in redacted
    assert "[REDACTED]" in redacted


# ==============================================================================
# 3. SSRF Defense & IP Validation Tests
# ==============================================================================

@pytest.mark.parametrize("ip_str", [
    "127.0.0.1",
    "10.0.0.5",
    "172.16.0.1",
    "192.168.1.100",
    "169.254.169.254",  # AWS metadata endpoint
    "::1",
    "fe80::1",
    "fc00::1",
])
def test_ssrf_blocking_private_ips(ip_str):
    """Verify internal and loopback IP addresses are flagged as private."""
    assert is_private_ip(ip_str) is True


def test_public_ip_not_blocked():
    """Ensure genuine public IP addresses pass the check."""
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("1.1.1.1") is False


@pytest.mark.asyncio
async def test_validate_and_fetch_url_scheme_validation():
    """Verify file://, ftp:// and gopher:// schemes are rejected."""
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        await validate_and_fetch_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        await validate_and_fetch_url("ftp://ftp.example.com/test.jpg")


@pytest.mark.asyncio
async def test_validate_and_fetch_url_blocks_localhost():
    """Verify localhost is rejected by SSRF protection."""
    with pytest.raises(ValueError, match="is blocked"):
        await validate_and_fetch_url("http://127.0.0.1/test.jpg")


# ==============================================================================
# 4. Image Decoding Tests
# ==============================================================================

def test_decode_base64_image_valid():
    """Verify valid Base64 image decodes successfully."""
    img = Image.new("RGB", (32, 32), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64_str = base64.b64encode(buf.getvalue()).decode()

    # Plain base64
    raw1 = decode_base64_image(b64_str)
    assert len(raw1) > 0

    # Data URI base64
    raw2 = decode_base64_image(f"data:image/jpeg;base64,{b64_str}")
    assert raw1 == raw2


def test_decode_base64_image_invalid():
    """Verify corrupted base64 or non-image is rejected."""
    with pytest.raises(ValueError, match="Invalid base64 encoding"):
        decode_base64_image("NotValidBase64@@@")

    # Valid base64 but text content
    fake_img_b64 = base64.b64encode(b"This is a text file, not an image").decode()
    with pytest.raises(ValueError, match="Decoded data is not a valid image"):
        decode_base64_image(fake_img_b64)


# ==============================================================================
# 5. Tool Unit Tests (Mocked Backend)
# ==============================================================================

@pytest.mark.asyncio
async def test_search_products_success():
    """Test search_products formats products cleanly."""
    mock_response = {
        "count": 1,
        "page": 1,
        "page_size": 10,
        "products": [
            {
                "code": "8906112662803",
                "product_name": "True Elements Muesli",
                "brands": "True Elements",
                "quantity": "1 kg",
                "nutriscore_grade": "a",
                "nova_group": 1,
                "image_front_small_url": "https://images.openfoodfacts.org/test.jpg",
            }
        ],
    }

    with patch.object(server.backend, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await search_products(query="muesli", page_size=5)

        assert result["total_matches"] == 1
        assert len(result["products"]) == 1
        p = result["products"][0]
        assert p["code"] == "8906112662803"
        assert p["product_name"] == "True Elements Muesli"
        assert p["nutriscore_grade"] == "A"
        assert p["nova_group"] == 1


@pytest.mark.asyncio
async def test_search_products_empty():
    """Test search_products handles empty result honestly."""
    with patch.object(server.backend, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"count": 0, "products": []}
        result = await search_products(query="nonexistent_snack_xyz", page_size=10)

        assert result["total_matches"] == 0
        assert result["products"] == []
        assert "No products found" in result["summary"]


@pytest.mark.asyncio
async def test_search_products_empty_query():
    """Test empty query rejection."""
    result = await search_products(query="   ")
    assert "error" in result


@pytest.mark.asyncio
async def test_get_product_details_found():
    """Test get_product_details extracts nutrition and ingredients."""
    mock_product = {
        "code": "8906112662803",
        "product": {
            "product_name": "True Elements Muesli",
            "brands": "True Elements",
            "quantity": "1 kg",
            "nutriscore_grade": "a",
            "nova_group": 1,
            "ingredients": [
                {"text": "Rolled Oats", "percent": 35.4},
                {"text": "Wheat Flakes", "percent": 25.0},
            ],
            "nutriments": {
                "energy-kcal_100g": 425,
                "proteins_100g": 13.5,
                "sugars_100g": 4.2,
                "fat_100g": 9.1,
                "fiber_100g": 10.8,
            },
            "allergens_tags": ["en:gluten"],
            "labels_tags": ["en:palm-oil-free", "en:vegetarian"],
            "completeness": 0.69,
        },
    }

    with patch.object(server.backend, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_product
        result = await get_product_details(barcode="8906112662803")

        assert result["found"] is True
        assert result["barcode"] == "8906112662803"
        assert result["product_name"] == "True Elements Muesli"
        assert result["nutrition_per_100g"]["protein_g"] == 13.5
        assert result["nutrition_per_100g"]["sugars_g"] == 4.2
        assert "Rolled Oats (35.4%)" in result["ingredients"]
        assert "gluten" in result["allergens"]
        assert "palm-oil-free" in result["labels"]


@pytest.mark.asyncio
async def test_get_product_details_not_found():
    """Test get_product_details returns honest not found for 404."""
    with patch.object(server.backend, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"_status": 404, "_detail": "Product not found"}
        result = await get_product_details(barcode="0000000000000")

        assert result["found"] is False
        assert "registered in Open Food Facts" in result["message"]


@pytest.mark.asyncio
async def test_find_product_prices_verified():
    """Test find_product_prices computes unit price per 100g."""
    mock_prices = {
        "listings": [
            {
                "retailer": "Blinkit",
                "price_inr": 346.0,
                "mrp_inr": 450.0,
                "pack_size": "1 kg",
                "url": "https://blinkit.com/item/123",
                "checked_at": "2026-10-23T10:00:00Z",
            }
        ]
    }

    with patch.object(server.backend, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_prices
        result = await find_product_prices(product_name="True Elements Muesli", pack_size="1kg")

        assert result["listings_count"] == 1
        item = result["listings"][0]
        assert item["retailer"] == "Blinkit"
        assert item["price_inr"] == 346.0
        # 346 / 1000g * 100g = 34.6
        assert item["price_per_100g"] == 34.6
        assert result["cheapest_store_per_100g"]["retailer"] == "Blinkit"


@pytest.mark.asyncio
async def test_check_ingredient_preferences_violation():
    """Test preference checking detects palm oil and sugar violations."""
    ingredients = ["Rolled Oats", "Palmolein Oil", "Maltodextrin", "Almonds"]
    result = await check_ingredient_preferences(
        excluded_ingredients=["palm oil", "sugar"],
        ingredients=ingredients,
    )

    assert result["status"] == "VIOLATION_DETECTED"
    assert result["violations_found"] == 2
    flagged = [v["ingredient"] for v in result["flagged_ingredients"]]
    assert "Palmolein Oil" in flagged
    assert "Maltodextrin" in flagged
    assert "Rolled Oats" in result["safe_ingredients"]
    assert "disclaimer" in result


@pytest.mark.asyncio
async def test_check_ingredient_preferences_clear():
    """Test preference checking confirms zero violations on clean product."""
    ingredients = ["Whole Grain Rolled Oats", "Raw Almonds", "Chia Seeds"]
    result = await check_ingredient_preferences(
        excluded_ingredients=["palm oil", "artificial sweeteners"],
        ingredients=ingredients,
    )

    assert result["status"] == "CLEAR"
    assert result["violations_found"] == 0
    assert len(result["safe_ingredients"]) == 3
