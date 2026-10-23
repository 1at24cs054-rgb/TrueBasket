"""Great Generator: Isolated Development & Testing Fixture Generator for TrueBasket.

IMPORTANT SAFETY & ARCHITECTURAL CONSTRAINTS:
1. This module is strictly an isolated development and testing utility.
2. It generates synthetic test fixtures (OriginalProduct, VisualLabelExtraction, NormalizedAlternative, RetailerListing, etc.)
   for offline automated unit/integration tests without making external network calls.
3. NEVER use in production runtime or user-facing request paths.
4. NEVER present synthetic data as real ingredients, nutrition facts, prices, or evidence.
5. Preserves all existing models, schemas, and live API integrations.
"""

from datetime import datetime, timezone
import io
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw

from app.schemas import (
    NormalizedAlternative,
    NormalizedNutrition,
    OriginalProduct,
    ProductImageCandidate,
    RetailerListing,
    SourceReference,
    VisualLabelExtraction,
)


class GreatGenerator:
    """Synthetic test fixture generator for TrueBasket schemas and models."""

    @staticmethod
    def generate_image_bytes(
        width: int = 400,
        height: int = 400,
        fmt: str = "JPEG",
        label_text: Optional[str] = "SYNTHETIC_TEST_FIXTURE",
    ) -> bytes:
        """Generate a valid in-memory image binary for testing visual pipelines."""
        mode = "RGBA" if fmt.upper() == "PNG" else "RGB"
        img = Image.new(mode, (width, height), color=(240, 240, 240))
        if label_text:
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), f"[FIXTURE] {label_text}", fill=(100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    @staticmethod
    def generate_visual_label_extraction(
        label_type: str = "back_of_pack",
        is_complete: bool = True,
        is_readable: bool = True,
        confidence: str = "high",
        ingredient_list: Optional[List[str]] = None,
        declared_percentages: Optional[Dict[str, float]] = None,
        nutrition_facts: Optional[Dict[str, Any]] = None,
        nutrition_basis: str = "per_100g",
        serving_size_g: Optional[float] = 40.0,
        allergen_declarations: Optional[List[str]] = None,
        extraction_status: str = "complete",
        image_ref: str = "synthetic://fixture/label_001.jpg",
    ) -> VisualLabelExtraction:
        """Create a synthetic VisualLabelExtraction fixture for testing."""
        if ingredient_list is None:
            ingredient_list = [
                "Rolled Oats", "Almonds", "Dried Cranberries", "Pumpkin Seeds", "Chia Seeds"
            ]
        if declared_percentages is None:
            declared_percentages = {"Rolled Oats": 50.0, "Almonds": 12.0}
        if nutrition_facts is None:
            nutrition_facts = {
                "energy_kcal": 420.0,
                "protein_g": 12.5,
                "dietary_fibre_g": 9.0,
                "total_sugar_g": 8.0,
                "added_sugar_g": 0.0,
                "total_fat_g": 8.5,
                "saturated_fat_g": 1.2,
                "sodium_mg": 40.0,
            }
        if allergen_declarations is None:
            allergen_declarations = ["Contains Almonds, Oats. May contain traces of soy."]

        return VisualLabelExtraction(
            image_url_or_ref=image_ref,
            label_type=label_type,
            is_readable=is_readable,
            is_complete=is_complete,
            confidence=confidence,
            ingredient_list=ingredient_list,
            declared_percentages=declared_percentages,
            nutrition_facts=nutrition_facts,
            nutrition_basis=nutrition_basis,
            serving_size_g=serving_size_g,
            allergen_declarations=allergen_declarations,
            extraction_status=extraction_status,
            conflicting_evidence=[],
        )

    @staticmethod
    def generate_original_product(
        brand: str = "SyntheticBrand",
        product_name: str = "Synthetic Muesli",
        variant: str = "Almond & Raisin",
        net_weight: str = "400g",
        panel_type: str = "back_of_pack",
        ingredient_panel_missing: bool = False,
        with_visual_extraction: bool = True,
    ) -> OriginalProduct:
        """Create a synthetic OriginalProduct fixture."""
        visual_ext = (
            GreatGenerator.generate_visual_label_extraction(label_type=panel_type)
            if with_visual_extraction
            else None
        )
        return OriginalProduct(
            brand=brand,
            product_name=product_name,
            variant=variant,
            net_weight=net_weight,
            serving_size="40g",
            ingredient_list=["Rolled Oats", "Almonds", "Raisins"] if not ingredient_panel_missing else [],
            declared_percentages={"Rolled Oats": 50.0} if not ingredient_panel_missing else {},
            nutrition_facts={"protein_g": 11.0, "dietary_fibre_g": 8.0} if not ingredient_panel_missing else {},
            allergen_warnings=["Contains Almonds"],
            barcode="8901234567890",
            fssai_license="10012345678901",
            manufacturer="Synthetic Foods Pvt Ltd",
            panel_type=panel_type,
            ingredient_panel_missing=ingredient_panel_missing,
            visual_extraction=visual_ext,
        )

    @staticmethod
    def generate_retailer_listing(
        retailer_name: str = "BigBasket",
        product_url: str = "https://example.com/product/123",
        listed_price_inr: float = 299.0,
        pack_size_raw: str = "400 g",
    ) -> RetailerListing:
        """Create a synthetic RetailerListing fixture."""
        return RetailerListing(
            retailer_name=retailer_name,
            product_url=product_url,
            pack_size_raw=pack_size_raw,
            listed_price_inr=listed_price_inr,
            mrp_inr=listed_price_inr * 1.15,
            discount_percentage=13.0,
            retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
            is_verified_listing=True,
        )

    @staticmethod
    def generate_candidate(
        brand: str = "TestCompetitor",
        product_name: str = "Super Crunch Cereal",
        pack_weight_g: float = 400.0,
        listed_price_inr: float = 280.0,
        label_status: str = "complete",
        with_nutrition: bool = True,
    ) -> NormalizedAlternative:
        """Create a synthetic NormalizedAlternative candidate fixture."""
        p100 = round((listed_price_inr / pack_weight_g) * 100.0, 2) if pack_weight_g else None
        nutri = None
        if with_nutrition and label_status in ("complete", "partial"):
            nutri = NormalizedNutrition(
                serving_basis="per_100g",
                energy_kcal=415.0,
                protein_g=12.0,
                fibre_g=8.5,
                total_sugar_g=7.0,
                added_sugar_g=0.0,
                total_fat_g=7.0,
                saturated_fat_g=1.1,
            )

        listing = GreatGenerator.generate_retailer_listing(
            retailer_name="Blinkit",
            listed_price_inr=listed_price_inr,
            pack_size_raw=f"{pack_weight_g}g",
        )

        visual_ext = (
            GreatGenerator.generate_visual_label_extraction(label_type="back_of_pack", extraction_status=label_status)
            if label_status in ("complete", "partial")
            else None
        )

        missing = []
        if label_status == "no_label_image_found":
            missing = ["packaging_label_image", "unverified_ingredients", "unverified_nutrition_table"]

        return NormalizedAlternative(
            brand=brand,
            product_name=product_name,
            pack_weight_g=pack_weight_g,
            unit_basis="g",
            listed_price_inr=listed_price_inr,
            price_per_100g=p100,
            nutrition_per_100g=nutri,
            ingredient_list=["Rolled Oats", "Almonds", "Seeds"] if label_status in ("complete", "partial") else [],
            declared_percentages={"Rolled Oats": 45.0} if label_status == "complete" else {},
            known_allergens=["Contains Nuts"] if label_status in ("complete", "partial") else [],
            retailer_listings=[listing],
            primary_product_url=listing.product_url,
            price_retrieval_timestamp=listing.retrieval_timestamp,
            data_confidence="high" if label_status == "complete" else "medium",
            missing_fields=missing,
            suitability_status="suitable",
            label_extraction_status=label_status,
            visual_extraction=visual_ext,
            candidate_images=[
                ProductImageCandidate(
                    image_url="https://example.com/test_pack.jpg",
                    image_type="back_of_pack",
                    retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
                    is_accessible=True,
                )
            ] if label_status != "no_label_image_found" else [],
        )

    @staticmethod
    def generate_candidate_batch(count: int = 3) -> List[NormalizedAlternative]:
        """Generate a diverse batch of candidate alternatives for comparison testing."""
        presets = [
            ("WholeTruth", "Clean Grain Muesli", 400.0, 340.0, "complete"),
            ("YogaBar", "High Protein Muesli", 400.0, 275.0, "complete"),
            ("BudgetGrains", "Classic Rolled Oats Mix", 500.0, 180.0, "no_label_image_found"),
            ("BrandX", "Sugar Loaded Flakes", 350.0, 210.0, "partial"),
        ]
        candidates = []
        for i in range(min(count, len(presets))):
            brand, name, wt, price, status = presets[i]
            candidates.append(
                GreatGenerator.generate_candidate(
                    brand=brand,
                    product_name=name,
                    pack_weight_g=wt,
                    listed_price_inr=price,
                    label_status=status,
                )
            )
        return candidates

    @staticmethod
    def generate_search_sources(brand: str = "SampleBrand", count: int = 2) -> List[SourceReference]:
        """Generate synthetic SourceReference search citations for unit test mocks."""
        sources = []
        for i in range(count):
            sources.append(
                SourceReference(
                    title=f"{brand} Muesli Pack {i+1} on Retailer",
                    url=f"https://www.bigbasket.com/pd/{1000+i}/{brand.lower()}-muesli",
                    snippet=f"Buy {brand} Muesli online in India. Great breakfast cereal pack.",
                    source_type="retailer_or_web",
                    score=0.9 - (i * 0.1),
                    published_date=datetime.now(timezone.utc).isoformat(),
                )
            )
        return sources
