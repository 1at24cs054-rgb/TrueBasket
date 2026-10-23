"""TrueBasket Model Context Protocol (MCP) Server.

Exposes TrueBasket food intelligence, Gemma 4 vision analysis,
product search, ingredient preference checking, and multi-store pricing
as official MCP tools for AI assistants.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import ipaddress
import logging
import os
import re
import socket
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# Import official MCP SDK v2 (MCPServer)
from mcp.server.mcpserver import MCPServer


# ==============================================================================
# Configuration & Environment Settings
# ==============================================================================

class MCPSettings(BaseSettings):
    """Runtime configuration for TrueBasket MCP Server."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../truebasket-backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    truebasket_api_base_url: str = Field(
        default="http://127.0.0.1:8000",
        description="Base URL of running TrueBasket FastAPI backend",
    )
    mcp_host: str = Field(default="127.0.0.1", description="Host to bind MCP server")
    mcp_port: int = Field(default=8002, description="Port to bind MCP server")
    mcp_transport: str = Field(
        default="streamable-http",
        description="Transport: 'streamable-http' or 'stdio'",
    )
    mcp_streamable_http_path: str = Field(
        default="/mcp",
        description="HTTP route for streamable HTTP transport",
    )
    mcp_auth_token: Optional[str] = Field(
        default=None,
        description="Optional Bearer token for securing remote endpoints",
    )
    backend_timeout_seconds: float = Field(
        default=180.0,
        description="HTTP client timeout for backend calls in seconds",
    )
    log_level: str = Field(default="INFO", description="Logging level")


settings = MCPSettings()

# Configure logging with secret redaction
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] truebasket.mcp: %(message)s",
)
logger = logging.getLogger("truebasket.mcp")


def redact_secrets(text: str) -> str:
    """Redact sensitive keys and tokens from logs and error messages."""
    if not isinstance(text, str):
        return str(text)
    # Redact OpenRouter / OpenAI / Tavily keys and Bearer tokens
    text = re.sub(r"(sk-or-v1-[a-zA-Z0-9_-]{8})[a-zA-Z0-9_-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(tvly-[a-zA-Z0-9_-]{6})[a-zA-Z0-9_-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(Bearer\s+)[a-zA-Z0-9._-]{10,}", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    return text


# ==============================================================================
# Security: SSRF Protection & Image Validation
# ==============================================================================

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB limit
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}


def is_private_ip(ip_str: str) -> bool:
    """Return True if IP is loopback, link-local, private, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return True


async def validate_and_fetch_url(url: str) -> bytes:
    """Safely fetch image from URL with strict SSRF and size validation."""
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}. Only HTTP/HTTPS allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname.")

    # Resolve hostname to verify destination IP addresses
    loop = asyncio.get_running_loop()
    try:
        addr_info = await loop.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ValueError(f"Failed to resolve host '{hostname}': {e}") from e

    # Check each resolved IP
    for family, _, _, _, sockaddr in addr_info:
        ip_addr = sockaddr[0]
        if is_private_ip(ip_addr):
            raise ValueError(f"Destination IP '{ip_addr}' for '{hostname}' is blocked (private/internal).")

    # Safe to download
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        try:
            response = await client.get(url)
        except Exception as e:
            raise ValueError(f"Failed to download image from URL: {redact_secrets(str(e))}") from e

        if response.status_code != 200:
            raise ValueError(f"Image download failed with status {response.status_code}")

        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_IMAGE_BYTES:
            raise ValueError(f"Image exceeds size limit of {MAX_IMAGE_BYTES // (1024*1024)} MB.")

        content = response.content
        if len(content) > MAX_IMAGE_BYTES:
            raise ValueError(f"Downloaded image ({len(content)} bytes) exceeds 20 MB limit.")

        # Validate image format via Pillow
        try:
            with Image.open(io.BytesIO(content)) as img:
                fmt = img.format or "UNKNOWN"
                if fmt.upper() not in ALLOWED_IMAGE_FORMATS:
                    raise ValueError(f"Unsupported image format: {fmt}. Must be JPEG, PNG, or WebP.")
        except Exception as e:
            raise ValueError(f"Invalid image file: {e}") from e

        return content


def decode_base64_image(image_base64: str) -> bytes:
    """Decode and validate base64 image data."""
    clean_b64 = image_base64.strip()
    if clean_b64.startswith("data:"):
        match = re.search(r"^data:[^;]+;base64,(.+)$", clean_b64, flags=re.DOTALL)
        if match:
            clean_b64 = match.group(1).strip()

    try:
        raw_bytes = base64.b64decode(clean_b64, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    if len(raw_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image payload ({len(raw_bytes)} bytes) exceeds maximum limit of 20 MB.")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            fmt = img.format or "UNKNOWN"
            if fmt.upper() not in ALLOWED_IMAGE_FORMATS:
                raise ValueError(f"Unsupported image format: {fmt}. Must be JPEG, PNG, or WebP.")
    except Exception as e:
        raise ValueError(f"Decoded data is not a valid image: {e}") from e

    return raw_bytes


# ==============================================================================
# Backend API Client Helper
# ==============================================================================

class BackendClient:
    """Async client for TrueBasket FastAPI backend."""

    def __init__(self, base_url: str, timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(url, params=params)
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Could not connect to TrueBasket backend at '{self.base_url}'. "
                    "Ensure the backend process is running (uvicorn app.main:app)."
                )
            except httpx.TimeoutException:
                raise RuntimeError(f"Request to '{endpoint}' timed out after {self.timeout}s.")

            if r.status_code == 404:
                return {"_status": 404, "_detail": r.text}
            if r.status_code != 200:
                raise RuntimeError(
                    f"Backend returned HTTP {r.status_code} for '{endpoint}': {redact_secrets(r.text[:300])}"
                )

            return r.json()

    async def post_multipart(
        self, endpoint: str, files: Dict[str, Any], data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.post(url, files=files, data=data)
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Could not connect to TrueBasket backend at '{self.base_url}'. "
                    "Ensure the backend process is running (uvicorn app.main:app)."
                )
            except httpx.TimeoutException:
                raise RuntimeError(f"Image analysis timed out after {self.timeout}s.")

            if r.status_code != 200:
                raise RuntimeError(
                    f"Backend returned HTTP {r.status_code} for '{endpoint}': {redact_secrets(r.text[:300])}"
                )

            return r.json()


backend = BackendClient(settings.truebasket_api_base_url, settings.backend_timeout_seconds)


# ==============================================================================
# Ingredient Synonym & Matching Engine
# ==============================================================================

SYNONYMS: Dict[str, List[str]] = {
    "palm oil": [
        "palm oil", "palmolein", "fractionated palm oil", "palm kernel oil",
        "hydrogenated palm oil", "refined palm oil", "elaeis guineensis"
    ],
    "sugar": [
        "sugar", "added sugar", "cane sugar", "sucrose", "glucose", "dextrose",
        "fructose", "corn syrup", "high fructose corn syrup", "maltodextrin",
        "invert sugar", "invert syrup", "golden syrup", "malt syrup", "molasses"
    ],
    "gluten": [
        "gluten", "wheat", "wheat flour", "maida", "atta", "barley", "rye",
        "spelt", "malt", "malted barley", "semolina", "suji"
    ],
    "dairy": [
        "milk", "dairy", "milk solids", "whey", "casein", "lactose", "butter",
        "cheese", "cream", "ghee", "milk powder", "skimmed milk"
    ],
    "nuts": [
        "peanuts", "almonds", "cashews", "walnuts", "pistachios", "hazelnuts",
        "tree nuts", "groundnuts", "macadamia"
    ],
    "soy": [
        "soy", "soya", "soybean", "soy lecithin", "soy protein", "hydrolyzed soy protein"
    ],
    "artificial sweeteners": [
        "aspartame", "sucralose", "acesulfame k", "acesulfame potassium",
        "saccharin", "cyclamate", "neotame", "advantame"
    ],
    "preservatives": [
        "sodium benzoate", "potassium sorbate", "sorbic acid", "sulphites",
        "sulfites", "sodium metabisulphite", "ins 211", "ins 202", "e211", "e202"
    ],
}


def matches_exclusion(ingredient: str, exclusion: str) -> bool:
    """Return True if ingredient matches the exclusion or any of its known synonyms."""
    clean_ing = ingredient.lower().strip()
    clean_ex = exclusion.lower().strip()

    if clean_ex in clean_ing:
        return True

    # Check synonyms
    for standard_term, syn_list in SYNONYMS.items():
        if clean_ex == standard_term or clean_ex in syn_list:
            for syn in syn_list:
                if syn in clean_ing:
                    return True

    return False


# ==============================================================================
# MCP Server Initialization
# ==============================================================================

mcp_app = MCPServer("TrueBasket")


# ==============================================================================
# Tool 1: search_products
# ==============================================================================

@mcp_app.tool()
async def search_products(query: str, page_size: int = 10) -> Dict[str, Any]:
    """Search for food products across the TrueBasket catalog and Open Food Facts.

    Args:
        query: Product name, brand name, category, or barcode (e.g. 'muesli', 'YogaBar', 'oats').
        page_size: Number of results to return (bounded between 1 and 50, default 10).

    Returns:
        Structured search results with product names, brands, barcodes, Nutri-Scores,
        NOVA groups, package quantities, and photos.
    """
    clean_query = query.strip()
    if not clean_query:
        return {"error": "Search query cannot be empty."}

    bounded_page_size = max(1, min(int(page_size), 50))
    data = await backend.get("/api/products/search", {"q": clean_query, "page_size": bounded_page_size})

    raw_products = data.get("products", [])
    total_count = data.get("count", len(raw_products))

    formatted_products = []
    for p in raw_products:
        formatted_products.append({
            "code": p.get("code") or p.get("id"),
            "product_name": p.get("product_name") or p.get("name") or "Unnamed Product",
            "brand": p.get("brands") or p.get("brand"),
            "quantity": p.get("quantity") or p.get("net_weight"),
            "nutriscore_grade": (p.get("nutriscore_grade") or "").upper() or None,
            "nova_group": p.get("nova_group"),
            "image_url": p.get("image_front_small_url") or p.get("image_url"),
        })

    return {
        "query": clean_query,
        "total_matches": total_count,
        "returned_count": len(formatted_products),
        "products": formatted_products,
        "summary": (
            f"Found {total_count} product(s) matching '{clean_query}'. "
            f"Displaying top {len(formatted_products)} results."
            if formatted_products
            else f"No products found in database matching '{clean_query}'."
        ),
    }


# ==============================================================================
# Tool 2: get_product_details
# ==============================================================================

@mcp_app.tool()
async def get_product_details(barcode: str) -> Dict[str, Any]:
    """Retrieve detailed nutrition facts, ingredient lists, allergens, and labels for a product.

    Args:
        barcode: The EAN or UPC barcode number of the packaged food product (e.g. '8906112662803').

    Returns:
        Complete product facts including declared ingredients, nutrient tables per 100g
        and per serving, Nutri-Score, NOVA classification, allergens, and data completeness.
    """
    clean_barcode = re.sub(r"\s+", "", str(barcode))
    if not clean_barcode:
        return {"error": "Barcode parameter cannot be empty."}

    data = await backend.get(f"/api/products/barcode/{clean_barcode}")
    if data.get("_status") == 404:
        return {
            "found": False,
            "barcode": clean_barcode,
            "message": f"No product with barcode {clean_barcode} is registered in Open Food Facts yet.",
        }

    raw = data.get("product") or {}
    nutriments = raw.get("nutriments") or {}

    # Extract clean nutrition values
    def parse_num(val):
        if val is None or val == "":
            return None
        try:
            return round(float(val), 2)
        except (ValueError, TypeError):
            return None

    nutrition_per_100g = {
        "energy_kcal": parse_num(nutriments.get("energy-kcal_100g") or nutriments.get("energy_100g")),
        "protein_g": parse_num(nutriments.get("proteins_100g")),
        "carbohydrates_g": parse_num(nutriments.get("carbohydrates_100g")),
        "sugars_g": parse_num(nutriments.get("sugars_100g")),
        "fat_g": parse_num(nutriments.get("fat_100g")),
        "saturated_fat_g": parse_num(nutriments.get("saturated-fat_100g")),
        "fiber_g": parse_num(nutriments.get("fiber_100g")),
        "sodium_mg": parse_num(nutriments.get("sodium_100g") * 1000 if nutriments.get("sodium_100g") is not None else None),
    }

    # Extract parsed ingredients
    ingredients_list = []
    if isinstance(raw.get("ingredients"), list):
        for ing in raw["ingredients"]:
            text = ing.get("text") or ing.get("id", "").replace("en:", "")
            pct = ing.get("percent_estimate") or ing.get("percent")
            if pct:
                ingredients_list.append(f"{text} ({round(pct, 1)}%)")
            elif text:
                ingredients_list.append(text)
    elif raw.get("ingredients_text"):
        ingredients_list = [i.strip() for i in raw["ingredients_text"].split(",") if i.strip()]

    return {
        "found": True,
        "barcode": clean_barcode,
        "product_name": raw.get("product_name") or raw.get("product_name_en") or "Unnamed Product",
        "brand": raw.get("brands"),
        "quantity": raw.get("quantity"),
        "nutriscore_grade": (raw.get("nutriscore_grade") or "").upper() or None,
        "nova_group": raw.get("nova_group"),
        "ingredients": ingredients_list,
        "ingredients_text": raw.get("ingredients_text"),
        "nutrition_per_100g": nutrition_per_100g,
        "serving_size": raw.get("serving_size"),
        "allergens": [a.replace("en:", "") for a in raw.get("allergens_tags", [])],
        "additives": [a.replace("en:", "") for a in raw.get("additives_tags", [])],
        "labels": [lbl.replace("en:", "") for lbl in raw.get("labels_tags", [])],
        "data_completeness_pct": round((raw.get("completeness") or 0) * 100, 1),
        "source_url": f"https://world.openfoodfacts.org/product/{clean_barcode}",
    }


# ==============================================================================
# Tool 3: analyze_food_image
# ==============================================================================

@mcp_app.tool()
async def analyze_food_image(
    image_base64: Optional[str] = None,
    image_url: Optional[str] = None,
    priority: str = "best_value",
    avoid_ingredients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Analyze a food-package photograph with Gemma 4 Vision to identify the product and extract labels.

    Args:
        image_base64: Base64-encoded image data or data URL (JPEG, PNG, or WebP up to 20MB).
        image_url: Public, safe URL pointing to the food-package photograph.
        priority: Recommendation priority: 'best_value', 'higher_fibre', 'lower_sugar', or 'minimal_additives'.
        avoid_ingredients: Optional list of ingredient strings to avoid (e.g. ['palm oil', 'maltodextrin']).

    Returns:
        Structured label extraction: identified brand, product name, visible ingredients,
        nutrition table, and evidence-backed alternative recommendations.
    """
    if not image_base64 and not image_url:
        return {"error": "Either 'image_base64' or 'image_url' must be provided."}

    # Fetch and validate image bytes
    try:
        if image_base64:
            image_bytes = decode_base64_image(image_base64)
        else:
            image_bytes = await validate_and_fetch_url(image_url)
    except Exception as e:
        return {"error": f"Image validation error: {str(e)}"}

    files = {"image": ("package.jpg", image_bytes, "image/jpeg")}
    data = {
        "priority": priority,
        "budget_inr": "",
        "pack_size_preference": "any",
        "avoid_ingredients": str(avoid_ingredients or []),
    }

    try:
        res = await backend.post_multipart("/api/products/analyze-image", files=files, data=data)
    except Exception as e:
        return {"error": f"Analysis failed: {redact_secrets(str(e))}"}

    orig = res.get("original_product") or {}
    panel_missing = orig.get("ingredient_panel_missing", False)

    notes = []
    if panel_missing:
        notes.append(
            "Notice: The uploaded photo is a front-of-pack image without an ingredients or nutrition panel. "
            "For full ingredient analysis, consider providing a photo of the back label."
        )

    return {
        "identified_product": {
            "brand": orig.get("brand"),
            "product_name": orig.get("product_name") or orig.get("name"),
            "variant": orig.get("variant"),
            "declared_net_weight": orig.get("net_weight"),
            "barcode": orig.get("barcode"),
            "panel_type": orig.get("panel_type"),
            "visible_ingredients": orig.get("ingredient_list", []),
            "declared_percentages": orig.get("declared_percentages", {}),
            "nutrition_facts": orig.get("nutrition_facts", {}),
            "allergen_warnings": orig.get("allergen_warnings", []),
        },
        "recommendations": res.get("recommendations", []),
        "rankings": res.get("rankings", []),
        "sources": res.get("sources", []),
        "guidance": notes,
    }


# ==============================================================================
# Tool 4: compare_alternatives
# ==============================================================================

@mcp_app.tool()
async def compare_alternatives(
    product_identifier: str,
    budget: Optional[float] = None,
    excluded_ingredients: Optional[List[str]] = None,
    priority: str = "best_value",
) -> Dict[str, Any]:
    """Find and rank genuinely healthier alternatives for a food product based on nutrition and price.

    Args:
        product_identifier: Product barcode or product search query (e.g. '8906112662803' or 'muesli').
        budget: Optional maximum budget in INR.
        excluded_ingredients: Optional list of ingredients to filter out (e.g. ['palm oil']).
        priority: Priority strategy ('best_value', 'higher_fibre', 'lower_sugar', 'minimal_additives').

    Returns:
        Top ranked alternatives with explicit health justifications and price differences.
    """
    clean_id = product_identifier.strip()
    if not clean_id:
        return {"error": "product_identifier cannot be empty."}

    # Step 1: If barcode, look up product and its category
    categories_tag = "en:mueslis"
    original_name = clean_id
    is_barcode = bool(re.match(r"^\d{8,14}$", clean_id))

    if is_barcode:
        p_data = await backend.get(f"/api/products/barcode/{clean_id}")
        if p_data.get("_status") != 404 and p_data.get("product"):
            prod = p_data["product"]
            original_name = prod.get("product_name") or prod.get("product_name_en") or clean_id
            tags = prod.get("categories_tags") or []
            if tags:
                categories_tag = tags[0]

    # Step 2: Fetch alternatives from backend
    data = await backend.get("/api/products/alternatives", {
        "categories_tags": categories_tag,
        "page_size": 25,
        "country": "india",
    })

    candidates = data.get("products", [])
    if not candidates:
        # Fallback to general search query
        search_res = await backend.get("/api/products/search", {"q": original_name, "page_size": 25})
        candidates = search_res.get("products", [])

    # Filter and rank candidates
    exclusions = excluded_ingredients or []
    ranked = []

    for c in candidates:
        name = c.get("product_name") or c.get("name") or "Unnamed"
        brand = c.get("brands") or c.get("brand") or "Generic"
        code = c.get("code") or c.get("id")

        # Skip the original product
        if is_barcode and code == clean_id:
            continue

        # Check ingredient exclusions
        ing_text = (c.get("ingredients_text") or "").lower()
        if any(matches_exclusion(ing_text, ex) for ex in exclusions):
            continue

        nutriments = c.get("nutriments") or {}
        sugar_g = nutriments.get("sugars_100g")
        fiber_g = nutriments.get("fiber_100g")
        protein_g = nutriments.get("proteins_100g")
        nutriscore = (c.get("nutriscore_grade") or "").upper()
        nova = c.get("nova_group")

        reasons = []
        badge = "Alternative"

        if fiber_g and fiber_g >= 6.0:
            reasons.append(f"High fibre ({fiber_g}g per 100g)")
            badge = "Higher Fibre"
        if sugar_g is not None and sugar_g <= 5.0:
            reasons.append(f"Low sugar ({sugar_g}g per 100g)")
            badge = "Low Sugar"
        if nova == 1:
            reasons.append("Minimally processed (NOVA 1)")
            badge = "Clean Ingredients"
        elif nutriscore == "A":
            reasons.append("Top nutritional rating (Nutri-Score A)")
            badge = "Nutri-Score A"

        ranked.append({
            "barcode": code,
            "product_name": name,
            "brand": brand,
            "badge": badge,
            "nutriscore_grade": nutriscore or "Unrated",
            "nova_group": nova or "Unrated",
            "sugar_100g": sugar_g,
            "fiber_100g": fiber_g,
            "protein_100g": protein_g,
            "reason": "; ".join(reasons) if reasons else "Balanced nutritional alternative",
            "image_url": c.get("image_front_small_url") or c.get("image_url"),
        })

    # Sort candidates by Nutri-Score (A > B > C) and fiber
    grade_order = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "Unrated": 6}
    ranked.sort(key=lambda x: (grade_order.get(x["nutriscore_grade"], 6), -(x["fiber_100g"] or 0)))

    return {
        "original_product": original_name,
        "alternatives_count": len(ranked[:5]),
        "recommended_alternatives": ranked[:5],
        "applied_filters": {
            "budget": budget,
            "excluded_ingredients": exclusions,
            "priority": priority,
        },
    }


# ==============================================================================
# Tool 5: find_product_prices
# ==============================================================================

@mcp_app.tool()
async def find_product_prices(
    product_name: str,
    barcode: Optional[str] = None,
    pincode: Optional[str] = None,
    pack_size: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve live pricing observations across stores (Blinkit, Zepto, Amazon Fresh, Instamart).

    Args:
        product_name: Full product name to search (e.g. 'True Elements Muesli 1 Kg').
        barcode: Optional barcode for precise price matching.
        pincode: Optional 6-digit Indian PIN code to locate regional store prices.
        pack_size: Optional package quantity (e.g. '500g', '1kg').

    Returns:
        Verified store prices, MRP discounts, unit prices per 100g, and retailer links.
    """
    clean_name = product_name.strip()
    if not clean_name:
        return {"error": "product_name cannot be empty."}

    params = {"query": clean_name}
    if barcode:
        params["barcode"] = barcode.strip()
    if pincode:
        params["pincode"] = pincode.strip()

    data = await backend.get("/api/prices", params)
    raw_listings = data.get("listings", [])

    parsed_listings = []
    cheapest = None
    min_per_100g = float("inf")

    for item in raw_listings:
        price = item.get("price_inr") or item.get("price")
        mrp = item.get("mrp_inr") or item.get("mrp")
        size = item.get("pack_size")
        retailer = item.get("retailer") or item.get("retailer_name")

        # Calculate unit price per 100g
        per_100g = None
        if price:
            size_str = str(size or pack_size or "")
            match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)", size_str, flags=re.I)
            if match:
                qty = float(match.group(1))
                unit = match.group(2).lower()
                grams = qty * 1000 if unit in ("kg", "l") else qty
                if grams > 0:
                    per_100g = round((float(price) / grams) * 100, 2)
                    if per_100g < min_per_100g:
                        min_per_100g = per_100g
                        cheapest = {"retailer": retailer, "price_per_100g": per_100g}

        parsed_listings.append({
            "retailer": retailer,
            "price_inr": price,
            "mrp_inr": mrp,
            "pack_size": size or pack_size or "Standard",
            "price_per_100g": per_100g,
            "url": item.get("url") or item.get("product_url"),
            "checked_at": item.get("checked_at") or item.get("retrieval_timestamp"),
        })

    return {
        "product_query": clean_name,
        "barcode": barcode,
        "listings_count": len(parsed_listings),
        "listings": parsed_listings,
        "cheapest_store_per_100g": cheapest,
        "status": "Prices verified" if parsed_listings else "No live store listings found",
    }


# ==============================================================================
# Tool 6: check_ingredient_preferences
# ==============================================================================

@mcp_app.tool()
async def check_ingredient_preferences(
    excluded_ingredients: List[str],
    product_identifier: Optional[str] = None,
    ingredients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Audit a product's ingredient list against dietary preferences and allergy exclusions.

    Args:
        excluded_ingredients: List of ingredients to avoid (e.g. ['palm oil', 'sugar', 'peanuts']).
        product_identifier: Optional barcode to look up ingredients automatically.
        ingredients: Optional explicit list of ingredient strings to audit.

    Returns:
        Structured compliance audit: flagged violations, verified ingredients, and a safety status.
    """
    if not excluded_ingredients:
        return {"error": "excluded_ingredients list cannot be empty."}

    # Retrieve ingredients if only product_identifier was given
    ing_list = ingredients or []
    product_name = None

    if not ing_list and product_identifier:
        clean_id = product_identifier.strip()
        p_data = await backend.get(f"/api/products/barcode/{clean_id}")
        if p_data.get("_status") != 404 and p_data.get("product"):
            prod = p_data["product"]
            product_name = prod.get("product_name")
            if isinstance(prod.get("ingredients"), list):
                ing_list = [i.get("text") or i.get("id", "") for i in prod["ingredients"]]
            elif prod.get("ingredients_text"):
                ing_list = [i.strip() for i in prod["ingredients_text"].split(",")]

    if not ing_list:
        return {
            "status": "UNKNOWN",
            "error": "No ingredient list was provided or found for this product.",
            "disclaimer": "Cannot evaluate ingredients without a verified packaging declaration.",
        }

    violations = []
    safe_ingredients = []

    for ing in ing_list:
        clean_ing = str(ing).strip()
        if not clean_ing:
            continue

        matched_ex = [ex for ex in excluded_ingredients if matches_exclusion(clean_ing, ex)]
        if matched_ex:
            violations.append({
                "ingredient": clean_ing,
                "matched_exclusions": matched_ex,
            })
        else:
            safe_ingredients.append(clean_ing)

    status = "VIOLATION_DETECTED" if violations else "CLEAR"

    return {
        "status": status,
        "product_name": product_name,
        "total_ingredients_audited": len(ing_list),
        "violations_found": len(violations),
        "flagged_ingredients": violations,
        "safe_ingredients": safe_ingredients,
        "summary": (
            f"Alert: Product contains {len(violations)} ingredient(s) matching your exclusion preferences."
            if violations
            else "All ingredients passed your exclusion criteria."
        ),
        "disclaimer": (
            "This analysis is informational and based on visible package declarations or public database records. "
            "It does not replace professional medical or clinical allergy advice."
        ),
    }


# ==============================================================================
# Authentication Middleware & HTTP App Factory
# ==============================================================================

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware to enforce Bearer token authentication on remote requests."""

    def __init__(self, app, auth_token: str):
        super().__init__(app)
        self.auth_token = auth_token

    async def dispatch(self, request: Request, call_next):
        # Health check is public
        if request.url.path == "/health":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Unauthorized: Missing or invalid Bearer token"}, status_code=401)

        token = auth_header.split(" ", 1)[1].strip()
        if token != self.auth_token:
            return JSONResponse({"error": "Forbidden: Invalid token"}, status_code=403)

        return await call_next(request)


def create_streamable_http_app():
    """Create and configure the Starlette app for streamable-http MCP transport."""
    starlette_app = mcp_app.streamable_http_app(
        streamable_http_path=settings.mcp_streamable_http_path,
        host=settings.mcp_host,
    )

    # Add health check route
    async def health(request: Request):
        return JSONResponse({
            "status": "ok",
            "server": "TrueBasket MCP Server",
            "version": "1.0.0",
            "backend_url": settings.truebasket_api_base_url,
            "transport": "streamable-http",
            "tools_registered": [
                "search_products",
                "get_product_details",
                "analyze_food_image",
                "compare_alternatives",
                "find_product_prices",
                "check_ingredient_preferences",
            ],
        })

    starlette_app.routes.append(Route("/health", health, methods=["GET"]))

    # Add auth middleware if token is set
    if settings.mcp_auth_token:
        logger.info("Securing MCP HTTP endpoint with Bearer authentication token.")
        starlette_app.add_middleware(BearerAuthMiddleware, auth_token=settings.mcp_auth_token)

    return starlette_app


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    """Parse arguments and start TrueBasket MCP server."""
    parser = argparse.ArgumentParser(description="TrueBasket Model Context Protocol (MCP) Server")
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "stdio", "sse"],
        default=settings.mcp_transport,
        help="MCP transport type (default: streamable-http)",
    )
    parser.add_argument(
        "--host",
        default=settings.mcp_host,
        help="Host to bind for HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.mcp_port,
        help="Port to bind for HTTP transports (default: 8001)",
    )
    parser.add_argument(
        "--backend-url",
        default=None,
        help="Base URL of TrueBasket backend (overrides TRUEBASKET_API_BASE_URL)",
    )

    args = parser.parse_args()

    if args.backend_url:
        settings.truebasket_api_base_url = args.backend_url
        backend.base_url = args.backend_url.rstrip("/")

    logger.info("Initializing TrueBasket MCP Server v1.0.0")
    logger.info(f"Target Backend API: {settings.truebasket_api_base_url}")
    logger.info(f"Selected Transport: {args.transport}")

    if args.transport == "stdio":
        logger.info("Running on stdio transport for local MCP client...")
        mcp_app.run(transport="stdio")
    else:
        logger.info(f"Running streamable-http server on http://{args.host}:{args.port}{settings.mcp_streamable_http_path}")
        logger.info(f"Health endpoint available at http://{args.host}:{args.port}/health")
        import uvicorn
        starlette_app = create_streamable_http_app()
        uvicorn.run(starlette_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
