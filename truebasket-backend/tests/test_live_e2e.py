import io
import json
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.skip(reason="Live provider end-to-end test; run standalone with python -m tests.test_live_e2e")
def test_live_end_to_end_pipeline():
    run()

def run():
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 20), "YogaBar Super Muesli - Fruits, Nuts & Seeds", fill=(0, 0, 0))
    d.text((20, 50), "Net Weight: 400g | Serving Size: 40g", fill=(0, 0, 0))
    d.text((20, 80), "Ingredients: Rolled Oats (50%), Almonds (12%), Raisins (8%), Chia Seeds, Palmolein, Sugar, INS 322", fill=(0, 0, 0))
    d.text((20, 110), "Nutrition Facts per 100g: Energy 410kcal, Protein 12g, Total Sugars 9g, Added Sugars 2g, Fibre 8.5g", fill=(0, 0, 0))
    d.text((20, 140), "Allergens: Contains Almonds, Nuts, Gluten", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    client = TestClient(app)
    resp = client.post(
        "/api/products/analyze-image",
        files={"image": ("yogabar_muesli.jpg", img_bytes, "image/jpeg")},
        data={"priority": "balanced", "avoid_ingredients": '["palmolein", "sugar"]'},
    )

    print("STATUS:", resp.status_code)
    data = resp.json()
    print("BRAND:", data.get("original_product", {}).get("brand"))
    print("PRODUCT:", data.get("original_product", {}).get("product_name"))
    print("INGREDIENTS:", data.get("original_product", {}).get("ingredient_list"))
    print("SOURCES COUNT:", len(data.get("sources", [])))
    print("ALTERNATIVES DISCOVERED:", len(data.get("alternatives", [])))
    print("RANKED ALTERNATIVES:", len(data.get("rankings", [])))
    for r in data.get("rankings", [])[:3]:
        c = r.get("candidate", {})
        print(f"  [Rank {r.get('rank')}] {c.get('brand')} - {c.get('product_name')} | Score: {r.get('total_score')} | Unit: Rs.{c.get('price_per_100g')}/100g | Status: {c.get('suitability_status')}")

    recs = data.get("recommendations") or {}
    print("\n--- RECOMMENDATIONS ---")
    if recs.get("best_overall_value"):
        bov = recs["best_overall_value"]
        print(f"1. Best Overall Value: {bov.get('product', {}).get('brand')} {bov.get('product', {}).get('product_name')}")
        print(f"   Reason: {bov.get('selection_reason')}")
    if recs.get("cheapest_suitable"):
        cs = recs["cheapest_suitable"]
        print(f"2. Cheapest Suitable: {cs.get('product', {}).get('brand')} {cs.get('product', {}).get('product_name')}")
        print(f"   Reason: {cs.get('selection_reason')}")
    if recs.get("best_nutrition_match"):
        bnm = recs["best_nutrition_match"]
        print(f"3. Best Nutrition Match: {bnm.get('product', {}).get('brand')} {bnm.get('product', {}).get('product_name')}")
        print(f"   Reason: {bnm.get('selection_reason')}")

    print("\nRESEARCH STATUS:", data.get("research_status"))

if __name__ == "__main__":
    run()
