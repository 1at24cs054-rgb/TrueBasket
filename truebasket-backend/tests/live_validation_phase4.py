"""Live Phase 4 Validation Script.

Executes real-world end-to-end workflow:
1. Fetch a real packaged muesli photo (from Open Food Facts public repository).
2. Upload image to POST /api/products/analyze-image.
3. Identify original product and extract packaging details visually.
4. Discover real competitor packaging images using Tavily image search.
5. Extract facts from accessible back-of-pack labels visually via Gemma 4.
6. Compare products using only supported ingredient/nutrition facts.
7. Retrieve and separate prices.
8. Generate recommendations with source URLs and explicit uncertainties.
9. Report statistics on images found, readable panels, and verifiable prices.
"""

import asyncio
import io
import json
import sys
import httpx
from PIL import Image

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.main import app
from fastapi.testclient import TestClient

REAL_PRODUCT_IMAGE_URL = "https://m.media-amazon.com/images/I/71oZ78ChbUL.jpg"

async def run_live_validation():
    print("=" * 80)
    print("TRUEBASKET PHASE 4: LIVE BACKEND VALIDATION RUN")
    print("=" * 80)

    # 1. Fetch real product image
    print(f"\n[Step 1] Fetching real packaging image from {REAL_PRODUCT_IMAGE_URL}...")
    headers = {"User-Agent": "TrueBasket-Phase4-Validation/1.0"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(REAL_PRODUCT_IMAGE_URL, headers=headers)
        assert resp.status_code == 200, f"Failed to download test image: {resp.status_code}"
        real_image_bytes = resp.content

    print(f"  Downloaded {len(real_image_bytes)} bytes. MIME: {resp.headers.get('content-type')}")

    # Verify Pillow can open it
    with Image.open(io.BytesIO(real_image_bytes)) as img:
        print(f"  Image verified: {img.format} {img.size} {img.mode}")

    # 2. Upload to /api/products/analyze-image
    print("\n[Step 2] Sending image to POST /api/products/analyze-image...")
    test_client = TestClient(app)
    api_resp = test_client.post(
        "/api/products/analyze-image",
        files={"image": ("real_muesli_front.jpg", real_image_bytes, "image/jpeg")},
        data={
            "priority": "balanced",
            "avoid_ingredients": '["artificial sweetener"]',
        },
    )

    print(f"  API Status Code: {api_resp.status_code}")
    if api_resp.status_code not in (200, 422):
        print("Error detail:", api_resp.text)
        return

    data = api_resp.json()

    # 3. Original Product Perception
    orig = data.get("original_product", {})
    print("\n[Step 3] Original Product Visual Identification:")
    print(f"  Brand: {orig.get('brand')}")
    print(f"  Product Name: {orig.get('product_name')}")
    print(f"  Variant: {orig.get('variant')}")
    print(f"  Net Weight: {orig.get('net_weight')}")
    print(f"  Panel Type: {orig.get('panel_type')}")
    print(f"  Ingredient Panel Missing: {orig.get('ingredient_panel_missing')}")
    print(f"  Visual Extraction Status: {data.get('label_extraction_status')}")

    # 4. Competitor Discovery & Image Results
    alts = data.get("alternatives", [])
    print(f"\n[Step 4] Competitor Alternatives Discovered ({len(alts)} candidates):")
    total_images_found = 0
    usable_labels_found = 0
    readable_nutrition_panels = 0
    verifiable_prices = 0

    for idx, cand in enumerate(alts, 1):
        brand = cand.get("brand")
        name = cand.get("product_name")
        price = cand.get("listed_price_inr")
        p100 = cand.get("price_per_100g")
        img_candidates = cand.get("candidate_images", [])
        total_images_found += len(img_candidates)
        label_status = cand.get("label_extraction_status")
        nutri = cand.get("nutrition_per_100g")

        if label_status in ("complete", "partial"):
            usable_labels_found += 1
        if nutri and any(nutri.get(k) is not None for k in ["protein_g", "fibre_g", "total_sugar_g"]):
            readable_nutrition_panels += 1
        if price is not None and price > 0:
            verifiable_prices += 1

        print(f"\n  Candidate #{idx}: {brand} - {name}")
        print(f"    Listed Price: Rs. {price} (Unit: Rs. {p100}/100g)" if p100 else f"    Listed Price: Rs. {price}")
        print(f"    Retailer Links: {len(cand.get('retailer_listings', []))} listings")
        print(f"    Packaging Images Discovered: {len(img_candidates)}")
        for img in img_candidates[:2]:
            print(f"      - [{img.get('image_type')}] {img.get('image_url')[:70]}...")
        print(f"    Label Extraction Status: {label_status}")
        if cand.get("visual_extraction"):
            ve = cand["visual_extraction"]
            print(f"    Visual Extraction: type={ve.get('label_type')} readable={ve.get('is_readable')} complete={ve.get('is_complete')}")
            print(f"    Ingredients Found ({len(cand.get('ingredient_list', []))}): {cand.get('ingredient_list', [])[:5]}")
        print(f"    Missing Fields: {cand.get('missing_fields')}")

    # 5. Recommendations
    recs = data.get("recommendations") or {}
    print("\n[Step 5] Recommendation Slots:")
    for key, title in [
        ("best_overall_value", "Best Overall Value"),
        ("cheapest_suitable", "Cheapest Suitable Alternative"),
        ("best_nutrition_match", "Best Ingredient & Nutrition Match"),
    ]:
        item = recs.get(key)
        if item:
            prod = item.get("product", {})
            print(f"\n  * {title}: {prod.get('brand')} {prod.get('product_name')}")
            print(f"    Selection Reason: {item.get('selection_reason')}")
            print(f"    Evidence Summary: {item.get('evidence_summary')}")
            print(f"    Comparison with Original: {item.get('comparison_with_original')}")
            print(f"    Trade-offs: {item.get('trade_offs')}")
            print(f"    Missing/Uncertain Info: {item.get('missing_or_uncertain_info')}")
            if item.get("purchase_links"):
                first_link = item["purchase_links"][0]
                print(f"    Purchase Link: {first_link.get('retailer_name')} -> {first_link.get('product_url')}")
        else:
            print(f"\n  * {title}: [No qualified candidate]")

    # 6. Report Statistics
    print("\n" + "=" * 80)
    print("PHASE 4 REAL-WORLD VALIDATION METRICS:")
    print(f"  Total Competitor Candidates Discovered: {len(alts)}")
    print(f"  Total Packaging Images Discovered:      {total_images_found}")
    print(f"  Products with Usable Label Images:      {usable_labels_found}")
    print(f"  Products with Readable Nutrition Panels:{readable_nutrition_panels}")
    print(f"  Products with Verifiable Prices:        {verifiable_prices}")
    print(f"  Overall Pipeline Research Status:       {data.get('research_status')}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_live_validation())
