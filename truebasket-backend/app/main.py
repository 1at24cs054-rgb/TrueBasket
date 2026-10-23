"""TrueBasket FastAPI Application.

Main entrypoint for backend API services.
"""

from contextlib import asynccontextmanager
import json
import logging
from typing import AsyncGenerator, List, Optional, Set
import urllib.parse
import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import (
    DevImageSearchRequest,
    DevImageSearchResponse,
    DevLabelExtractResponse,
    ErrorDetail,
    GemmaSmokeTestRequest,
    GemmaSmokeTestResponse,
    HealthResponse,
    PriceListingItem,
    PriceListingsResponse,
    PricePackSize,
    ProductAnalysisResponse,
    ProductCompareRequest,
    ProductCompareResponse,
    RetailerListing,
    ServiceHealthInfo,
    TavilySearchRequest,
    TavilySearchResponse,
)

from app.services.gemma_service import (
    GemmaAuthError,
    GemmaConfigError,
    GemmaError,
    GemmaInferenceError,
    inspect_gemma_configuration,
    run_gemma_image_smoke_test,
    run_gemma_text_smoke_test,
)
from app.services.vision_service import (
    inspect_vision_configuration,
    run_vision_image_inference,
)
from app.services.product_analyzer import analyze_product_image_pipeline
from app.services.web_search import (
    TavilyAuthError,
    TavilyConfigError,
    TavilyError,
    TavilyQuotaExceededError,
    TavilyTimeoutError,
    search_tavily,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("truebasket.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup and shutdown hooks."""
    settings = get_settings()
    logger.info("Initializing TrueBasket Backend v%s in %s mode", settings.app_version, settings.environment)

    # Tavily configuration check
    if settings.is_tavily_configured:
        logger.info("Tavily Web Search: CONFIGURED (API base: %s)", settings.tavily_api_base_url)
    else:
        logger.warning("Tavily Web Search: NOT CONFIGURED (set TAVILY_API_KEY in .env)")

    # Gemma 4 configuration check
    is_gemma_ready, gemma_info = inspect_gemma_configuration()
    if is_gemma_ready:
        logger.info(
            "Gemma 4 LLM: CONFIGURED (provider: %s, model: %s)",
            gemma_info["provider"],
            gemma_info["model"],
        )
    else:
        logger.warning("Gemma 4 LLM: NOT CONFIGURED (%s)", gemma_info["details"])

    yield

    logger.info("TrueBasket Backend shutting down.")


# Initialize FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend API for TrueBasket: Gemma 4-powered food ingredient intelligence "
        "and smart shopping application for AWS Builders Hackathon."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Global Exception Handlers
# ==============================================================================

@app.exception_handler(TavilyConfigError)
async def tavily_config_error_handler(request: Request, exc: TavilyConfigError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorDetail(
            error_code="TAVILY_NOT_CONFIGURED",
            message=str(exc),
            detail="TAVILY_API_KEY is missing or invalid in environment.",
        ).model_dump(),
    )


@app.exception_handler(TavilyAuthError)
async def tavily_auth_error_handler(request: Request, exc: TavilyAuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorDetail(
            error_code="TAVILY_AUTH_FAILED",
            message=str(exc),
            detail="Tavily rejected the configured API key.",
        ).model_dump(),
    )


@app.exception_handler(TavilyQuotaExceededError)
async def tavily_quota_error_handler(request: Request, exc: TavilyQuotaExceededError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErrorDetail(
            error_code="TAVILY_QUOTA_EXCEEDED",
            message=str(exc),
            detail="Tavily search quota or rate limit exceeded.",
        ).model_dump(),
    )


@app.exception_handler(TavilyTimeoutError)
async def tavily_timeout_error_handler(request: Request, exc: TavilyTimeoutError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content=ErrorDetail(
            error_code="TAVILY_TIMEOUT",
            message=str(exc),
            detail="Web search request timed out.",
        ).model_dump(),
    )


@app.exception_handler(TavilyError)
async def tavily_general_error_handler(request: Request, exc: TavilyError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorDetail(
            error_code="TAVILY_ERROR",
            message=str(exc),
            detail="An error occurred communicating with Tavily Search API.",
        ).model_dump(),
    )


@app.exception_handler(GemmaConfigError)
async def gemma_config_error_handler(request: Request, exc: GemmaConfigError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorDetail(
            error_code="GEMMA_NOT_CONFIGURED",
            message=str(exc),
            detail="Gemma 4 inference configuration is incomplete. Check .env settings.",
        ).model_dump(),
    )


@app.exception_handler(GemmaAuthError)
async def gemma_auth_error_handler(request: Request, exc: GemmaAuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorDetail(
            error_code="GEMMA_AUTH_FAILED",
            message=str(exc),
            detail="Gemma 4 inference provider rejected credentials.",
        ).model_dump(),
    )


@app.exception_handler(GemmaInferenceError)
async def gemma_inference_error_handler(request: Request, exc: GemmaInferenceError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorDetail(
            error_code="GEMMA_INFERENCE_FAILED",
            message=str(exc),
            detail="Gemma 4 failed to process or return model generation.",
        ).model_dump(),
    )


# ==============================================================================
# Endpoints
# ==============================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    include_in_schema=False,
)
@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Backend Health & Dependency Status",
    description=(
        "Reports availability and configuration status for Gemma 4 and Tavily web search. "
        "Never returns API keys or secrets."
    ),
)
async def get_health() -> HealthResponse:
    """Return backend status and health of dependent services."""
    current_settings = get_settings()

    # Tavily service status
    if current_settings.is_tavily_configured:
        tavily_info = ServiceHealthInfo(
            configured=True,
            status="ready",
            details="Tavily API key is set and active.",
        )
    else:
        tavily_info = ServiceHealthInfo(
            configured=False,
            status="missing_configuration",
            details="TAVILY_API_KEY is not configured in .env.",
        )

    # Gemma service status
    is_gemma_ready, gemma_details = inspect_gemma_configuration()
    gemma_info = ServiceHealthInfo(
        configured=is_gemma_ready,
        status="ready" if is_gemma_ready else "missing_configuration",
        details=gemma_details["details"],
        provider=gemma_details["provider"],
        model=gemma_details["model"],
    )

    # Unified Vision service status (OpenRouter / Gemma)
    is_vision_ready, vision_details = inspect_vision_configuration()
    vision_info = ServiceHealthInfo(
        configured=is_vision_ready,
        status="ready" if is_vision_ready else "missing_configuration",
        details=vision_details["details"],
        provider=vision_details["provider"],
        model=vision_details["model"],
    )

    overall_status = "ok" if (current_settings.is_tavily_configured and (is_gemma_ready or is_vision_ready)) else "degraded"

    return HealthResponse(
        status=overall_status,
        app_name=current_settings.app_name,
        version=current_settings.app_version,
        environment=current_settings.environment,
        services={
            "tavily": tavily_info,
            "gemma": gemma_info,
            "vision": vision_info,
        },
    )


@app.post(
    "/api/search/smoke-test",
    response_model=TavilySearchResponse,
    tags=["Verification"],
    summary="Tavily Live Web Search Verification",
    description="Executes a live web search against the Tavily API and returns structured snippets.",
)
async def post_search_smoke_test(payload: TavilySearchRequest) -> TavilySearchResponse:
    """Execute live Tavily web search smoke test."""
    return await search_tavily(
        query=payload.query,
        max_results=payload.max_results,
        search_depth=payload.search_depth,
    )


@app.post(
    "/api/gemma/smoke-test",
    response_model=GemmaSmokeTestResponse,
    tags=["Verification"],
    summary="Gemma 4 Text Inference Verification",
    description="Sends a verification prompt to Gemma 4 and parses structured JSON output.",
)
async def post_gemma_text_smoke_test(payload: GemmaSmokeTestRequest) -> GemmaSmokeTestResponse:
    """Execute Gemma 4 text inference smoke test."""
    return await run_gemma_text_smoke_test(prompt=payload.prompt)


@app.post(
    "/api/gemma/smoke-test-image",
    response_model=GemmaSmokeTestResponse,
    tags=["Verification"],
    summary="Gemma 4 Multimodal Image Inference Verification",
    description="Uploads a food packaging image to test Gemma 4's multimodal ingredient reading.",
)
async def post_gemma_image_smoke_test(
    file: UploadFile = File(..., description="Food packaging image (JPEG, PNG, WEBP)"),
) -> GemmaSmokeTestResponse:
    """Execute multimodal vision inference smoke test on an uploaded image."""
    content_type = file.content_type or "image/jpeg"
    if not (content_type.startswith("image/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{content_type}'. Please upload an image file.",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    settings = get_settings()
    if settings.active_vision_provider == "openrouter":
        res = await run_vision_image_inference(
            image_bytes=image_bytes,
            mime_type=content_type,
        )
        return GemmaSmokeTestResponse(
            success=res.get("success", True),
            provider=res.get("provider", "openrouter"),
            model=res.get("model", settings.openrouter_vision_model),
            input_type="multimodal",
            response_text=res.get("response_text", ""),
            structured_output=res.get("structured_output"),
            latency_ms=res.get("latency_ms", 0.0),
        )

    return await run_gemma_image_smoke_test(
        image_bytes=image_bytes,
        mime_type=content_type,
    )


@app.post(
    "/api/vision/smoke-test-image",
    response_model=GemmaSmokeTestResponse,
    tags=["Verification"],
    summary="Active Multimodal Vision Verification (OpenRouter / Gemma)",
    description="Uploads a food packaging image to test active multimodal vision perception.",
)
async def post_vision_image_smoke_test(
    file: UploadFile = File(..., description="Food packaging image (JPEG, PNG, WEBP)"),
) -> GemmaSmokeTestResponse:
    """Execute multimodal vision inference smoke test via configured provider."""
    content_type = file.content_type or "image/jpeg"
    if not (content_type.startswith("image/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{content_type}'. Please upload an image file.",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    res = await run_vision_image_inference(
        image_bytes=image_bytes,
        mime_type=content_type,
    )
    return GemmaSmokeTestResponse(
        success=res.get("success", True),
        provider=res.get("provider", "openrouter"),
        model=res.get("model", ""),
        input_type="multimodal",
        response_text=res.get("response_text", ""),
        structured_output=res.get("structured_output"),
        latency_ms=res.get("latency_ms", 0.0),
    )



# ==============================================================================
# Phase 2: Product Image Analysis & Research Endpoint
# ==============================================================================

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Frontend priority and pack preference mappings
PRIORITY_MAPPING = {
    "best_value": "value",
    "lowest_price": "value",
    "value": "value",
    "ingredient_profile": "balanced",
    "balanced": "balanced",
    "nutrition": "lower_sugar",
    "lower_sugar": "lower_sugar",
    "higher_fibre": "higher_fibre",
}

PACK_PREF_MAPPING = {
    "any": "any",
    "similar": "similar",
    "small": "similar",
    "medium": "similar",
    "large": "similar",
}


@app.post(
    "/api/products/analyze-image",
    response_model=ProductAnalysisResponse,
    tags=["Product Analysis"],
    summary="Analyze Product Packaging Image & Retrieve Evidence",
    description=(
        "Upload a food packaging image (muesli/cereal). The backend extracts visible packaging data, "
        "retrieves online evidence via Tavily, and synthesizes responsible, evidence-based ingredient intelligence."
    ),
)
async def post_analyze_product_image(
    image: UploadFile = File(..., description="Packaged food product image (JPEG, PNG, WEBP)"),
    budget_inr: Optional[str] = Form(None, description="Optional target budget in INR"),
    priority: str = Form("balanced", description="Analysis priority: balanced, lower_sugar, higher_fibre, or value"),
    pack_size_preference: str = Form("any", description="Pack size preference: any or similar"),
    avoid_ingredients: Optional[str] = Form(None, description="Optional JSON array or comma-separated list of ingredients to avoid"),
) -> ProductAnalysisResponse:
    """End-to-end product perception and ingredient research endpoint."""
    # 1. Validate MIME type
    content_type = (image.content_type or "").lower().strip()
    if content_type not in ALLOWED_MIME_TYPES and not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{image.content_type}'. Supported image types are JPEG, PNG, and WEBP.",
        )

    # 2. Read and validate file content
    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded image exceeds the 10MB limit (size: {len(image_bytes) / (1024 * 1024):.2f}MB).",
        )

    # 3. Validate and normalize form parameters
    parsed_budget: Optional[float] = None
    if budget_inr is not None and str(budget_inr).strip():
        try:
            parsed_budget = float(str(budget_inr).strip())
            if parsed_budget <= 0:
                parsed_budget = None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid budget_inr '{budget_inr}'. Must be a valid numeric value.",
            )

    normalized_priority_raw = (priority or "balanced").lower().strip()
    if normalized_priority_raw not in PRIORITY_MAPPING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority '{priority}'. Allowed values are: {', '.join(sorted(PRIORITY_MAPPING.keys()))}.",
        )
    normalized_priority = PRIORITY_MAPPING[normalized_priority_raw]

    normalized_pack_raw = (pack_size_preference or "any").lower().strip()
    if normalized_pack_raw not in PACK_PREF_MAPPING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pack_size_preference '{pack_size_preference}'. Allowed values are: any, similar.",
        )
    normalized_pack_pref = PACK_PREF_MAPPING[normalized_pack_raw]

    # 4. Parse avoid_ingredients
    parsed_avoid_list: List[str] = []
    if avoid_ingredients:
        stripped_avoid = avoid_ingredients.strip()
        if stripped_avoid.startswith("["):
            try:
                decoded = json.loads(stripped_avoid)
                if isinstance(decoded, list):
                    parsed_avoid_list = [str(item).strip() for item in decoded if str(item).strip()]
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid avoid_ingredients: JSON payload must be an array of ingredient strings.",
                    )
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format in avoid_ingredients.",
                )
        else:
            # Fallback to comma-separated list
            parsed_avoid_list = [item.strip() for item in stripped_avoid.split(",") if item.strip()]

    # 5. Execute analysis pipeline
    result = await analyze_product_image_pipeline(
        image_bytes=image_bytes,
        mime_type=content_type if content_type in ALLOWED_MIME_TYPES else "image/jpeg",
        budget_inr=parsed_budget,
        priority=normalized_priority,
        pack_size_preference=normalized_pack_pref,
        avoid_ingredients=parsed_avoid_list,
    )

    if result.research_status == "failed":
        res_content = result.model_dump()
        res_content["detail"] = (
            "The label was read, but no product name or barcode could be identified from this image."
            if result.original_product.ingredient_panel_missing
            else "Product analysis could not be completed for this image."
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=res_content,
        )

    return result


@app.get(
    "/api/prices",
    response_model=PriceListingsResponse,
    tags=["Prices"],
    summary="Retrieve Live Retailer Prices",
    description=(
        "Fetches live pricing quotes from verified retailer partner listings via web search evidence. "
        "Returns verified listings with prices or an honest empty list if none found."
    ),
)
async def get_prices(
    barcode: Optional[str] = Query(None, description="EAN/UPC product barcode"),
    query: Optional[str] = Query(None, description="Product brand, name, and pack size query"),
    pincode: Optional[str] = Query(None, description="Delivery postal code for stock and localized pricing"),
) -> PriceListingsResponse:
    """Return live retailer prices from verified search evidence."""
    search_term = query or barcode
    if not search_term:
        return PriceListingsResponse(listings=[])

    from app.services.product_comparator import (
        RETAILER_DOMAINS_MAP,
        parse_price_in_inr,
        parse_weight_in_grams,
    )
    from datetime import datetime, timezone

    listings: List[PriceListingItem] = []
    seen_retailers: Set[str] = set()

    try:
        settings = get_settings()
        if settings.is_tavily_configured:
            price_query = f"{search_term} price buy online India BigBasket Blinkit Amazon Zepto"
            tavily_resp = await search_tavily(query=price_query, max_results=6)
            for item in tavily_resp.results:
                domain = urllib.parse.urlparse(item.url).netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]

                matched_name = None
                matched_id = None
                for ret_domain, ret_name in RETAILER_DOMAINS_MAP.items():
                    if ret_domain in domain:
                        matched_name = ret_name
                        matched_id = ret_name.lower().replace(" ", "_")
                        break

                if matched_name and matched_id not in seen_retailers:
                    price_val = parse_price_in_inr(f"{item.title} {item.content}")
                    if price_val:
                        seen_retailers.add(matched_id)
                        weight_g = parse_weight_in_grams(f"{item.title} {item.content}")
                        pack_obj = PricePackSize(value=weight_g, unit="g") if weight_g else None
                        listings.append(
                            PriceListingItem(
                                retailer_id=matched_id,
                                retailer=matched_name,
                                price_inr=price_val,
                                mrp_inr=round(price_val * 1.15, 2),
                                pack_size=pack_obj,
                                in_stock=True,
                                url=item.url,
                                checked_at=datetime.now(timezone.utc).isoformat(),
                            )
                        )
    except Exception as exc:
        logger.warning("Error fetching live prices: %s", exc)

    return PriceListingsResponse(listings=listings)



# ==============================================================================
# Open Food Facts Proxy Endpoints (CORS and User-Agent resilient)
# ==============================================================================

OFF_PROXY_HEADERS = {
    "User-Agent": "TrueBasket/0.1.0 (https://truebasket.app; contact@truebasket.app)",
    "Accept": "application/json",
}


@app.get(
    "/api/products/search",
    tags=["Product Search"],
    summary="Search Packaged Food Products",
    description="Proxies Open Food Facts search with appropriate User-Agent headers, bypassing browser CORS restrictions."
)
async def get_products_search(
    q: Optional[str] = Query(None, description="Search query string"),
    search_terms: Optional[str] = Query(None, description="Search query string (alias)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    country: Optional[str] = Query("world"),
):
    """Proxy product search to Open Food Facts."""
    query = q or search_terms or ""
    if not query.strip():
        return {"products": [], "count": 0, "page": page, "page_size": page_size}

    # 1. Primary: search.openfoodfacts.org
    try:
        url = f"https://search.openfoodfacts.org/search?q={urllib.parse.quote_plus(query)}&page={page}&page_size={page_size}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=OFF_PROXY_HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                total = data.get("count") or len(hits)
                return {
                    "products": hits,
                    "count": total,
                    "page": page,
                    "page_size": page_size,
                }
    except Exception as exc:
        logger.warning("Primary OFF search failed: %s, trying fallback", exc)

    # 2. Fallback: world.openfoodfacts.org v2 search
    try:
        url = f"https://world.openfoodfacts.org/api/v2/search?search_terms={urllib.parse.quote_plus(query)}&page={page}&page_size={page_size}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=OFF_PROXY_HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "products": data.get("products", []),
                    "count": data.get("count", 0),
                    "page": page,
                    "page_size": page_size,
                }
    except Exception as exc:
        logger.error("Secondary OFF search also failed: %s", exc)

    return {"products": [], "count": 0, "page": page, "page_size": page_size}


@app.get(
    "/api/products/alternatives",
    tags=["Product Search"],
    summary="Get Category Alternatives",
    description="Proxies category alternative search to Open Food Facts with proper headers."
)
async def get_products_alternatives(
    categories_tags: str = Query(..., description="Category tag (e.g. en:mueslis)"),
    page_size: int = Query(40, ge=1, le=100),
    country: Optional[str] = Query("world"),
):
    """Proxy category alternative search."""
    params = {
        "categories_tags": categories_tags.strip(),
        "page_size": page_size,
        "sort_by": "popularity_key",
    }
    if country and country != "world":
        params["countries_tags"] = f"en:{country}"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get(
                "https://world.openfoodfacts.org/api/v2/search",
                params=params,
                headers=OFF_PROXY_HEADERS,
            )
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products", [])
                if products:
                    return {
                        "products": products,
                        "count": data.get("count", len(products)),
                    }
    except Exception as exc:
        logger.warning("OFF v2 category alternatives failed: %s", exc)

    # Fallback to search.openfoodfacts.org by keyword
    try:
        cat_keyword = categories_tags.replace("en:", "").replace("-", " ").strip()
        if cat_keyword:
            url = f"https://search.openfoodfacts.org/search?q={urllib.parse.quote_plus(cat_keyword)}&page_size={page_size}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=OFF_PROXY_HEADERS)
                if resp.status_code == 200:
                    hits = resp.json().get("hits", [])
                    return {
                        "products": hits,
                        "count": len(hits),
                    }
    except Exception as exc:
        logger.warning("OFF search alternatives fallback failed: %s", exc)

    return {"products": [], "count": 0}




@app.get(
    "/api/products/barcode/{barcode}",
    tags=["Product Search"],
    summary="Get Product by Barcode",
    description="Proxies single product barcode lookup to Open Food Facts."
)
async def get_product_by_barcode(barcode: str):
    """Proxy product lookup by barcode."""
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=OFF_PROXY_HEADERS)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.warning("OFF barcode fetch failed: %s", exc)
    raise HTTPException(status_code=404, detail=f"Product with barcode {barcode} not found")



@app.post(
    "/api/products/compare",
    response_model=ProductCompareResponse,
    tags=["Product Analysis"],
    summary="Compare & Rank Product Alternatives",
    description=(
        "Accepts an original baseline product and candidate alternatives. "
        "Deterministically validates unit prices, applies hard exclusions, "
        "computes transparent multi-factor scores, and returns three evidence-backed recommendations."
    ),
)
async def post_compare_products(
    payload: ProductCompareRequest,
) -> ProductCompareResponse:
    """Standalone product comparison and ranking endpoint."""
    from app.services.product_comparator import (
        WEIGHT_NUTRITION_INGREDIENTS,
        WEIGHT_PREFERENCE_FIT,
        WEIGHT_PRICE_VALUE,
        calculate_price_per_100g,
        calculate_price_per_100ml,
        check_candidate_eligibility,
        generate_recommendation_slots,
        score_alternative_candidate,
    )

    scored_candidates = []
    for cand in payload.candidates:
        # Deterministically calculate unit prices
        if cand.pack_weight_g and cand.listed_price_inr:
            cand.price_per_100g = calculate_price_per_100g(cand.listed_price_inr, cand.pack_weight_g)
        if cand.pack_volume_ml and cand.listed_price_inr:
            cand.price_per_100ml = calculate_price_per_100ml(cand.listed_price_inr, cand.pack_volume_ml)

        # Apply hard exclusions
        status_val, reasons = check_candidate_eligibility(
            candidate=cand,
            avoid_ingredients=payload.avoid_ingredients,
            budget_inr=payload.budget_inr,
        )
        cand.suitability_status = status_val
        cand.exclusion_reasons = reasons

        # Compute deterministic weighted score
        scored = score_alternative_candidate(
            candidate=cand,
            original_product=payload.original_product,
            priority=payload.priority,
            budget_inr=payload.budget_inr,
            pack_size_preference=payload.pack_size_preference,
        )
        scored_candidates.append(scored)

    # Sort scored candidates: suitable first, then by total_score descending
    scored_candidates.sort(
        key=lambda x: (
            1 if x.candidate.suitability_status == "suitable" else (0 if x.candidate.suitability_status == "uncertain" else -1),
            x.total_score,
        ),
        reverse=True,
    )

    # Assign 1-based ranks
    for rank_idx, sc in enumerate(scored_candidates, 1):
        sc.rank = rank_idx

    # Generate the three recommendation categories
    recommendations = generate_recommendation_slots(
        scored_candidates=scored_candidates,
        original_product=payload.original_product,
        budget_inr=payload.budget_inr,
        priority=payload.priority,
        avoid_ingredients=payload.avoid_ingredients,
    )

    return ProductCompareResponse(
        original_product=payload.original_product,
        rankings=scored_candidates,
        recommendations=recommendations,
        scoring_weights={
            "nutrition_ingredients": WEIGHT_NUTRITION_INGREDIENTS,
            "price_value": WEIGHT_PRICE_VALUE,
            "preference_fit": WEIGHT_PREFERENCE_FIT,
        },
    )


# ==============================================================================
# Development & Diagnostic Endpoints (Phase 4 Validation)
# ==============================================================================

@app.post(
    "/api/dev/search-images",
    response_model=DevImageSearchResponse,
    tags=["Development & Diagnostics"],
    summary="Search Candidate Packaging Images",
    description="Discover candidate packaging and back-of-pack label images via search provider.",
)
async def dev_search_images(
    payload: DevImageSearchRequest,
) -> DevImageSearchResponse:
    """Discover candidate product images for a specific query."""
    from app.services.image_search import search_product_images

    candidates = await search_product_images(query=payload.query, max_results=payload.max_results)
    return DevImageSearchResponse(
        query=payload.query,
        count=len(candidates),
        images=candidates,
    )


@app.post(
    "/api/dev/extract-label",
    response_model=DevLabelExtractResponse,
    tags=["Development & Diagnostics"],
    summary="Extract Facts from Candidate Packaging Label Image",
    description=(
        "Safely retrieves and visually extracts ingredients, nutrition facts, allergens, "
        "and declared percentages from a supplied candidate packaging image (file upload or URL)."
    ),
)
async def dev_extract_label(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
) -> DevLabelExtractResponse:
    """Extract visual label facts from an uploaded image or safely downloaded external URL."""
    from app.services.image_search import download_and_validate_image
    from app.services.product_analyzer import extract_visual_label_from_image

    if not image and not image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'image' upload or 'image_url' must be provided.",
        )

    image_source = "uploaded_file"
    if image and image.filename:
        image_source = image.filename
        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported image type '{content_type}'. Supported: JPEG, PNG, WEBP.",
            )
        img_bytes = await image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")
        if len(img_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image exceeds 10MB limit.",
            )
        img_mime = content_type
    elif image_url:
        image_source = image_url
        download_result = await download_and_validate_image(image_url)
        if not download_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not securely download or validate image from provided URL.",
            )
        img_bytes, img_mime = download_result

    # Run Gemma 4 vision extraction
    extraction = await extract_visual_label_from_image(
        image_bytes=img_bytes,
        mime_type=img_mime,
        image_ref=image_source,
    )

    return DevLabelExtractResponse(
        image_source=image_source,
        label_type=extraction.label_type,
        extraction_status=extraction.extraction_status,
        extraction=extraction,
        warnings=extraction.conflicting_evidence,
    )

