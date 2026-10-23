"""Unit tests for GreatGenerator testing utility.

Verifies:
1. GreatGenerator produces valid test fixtures matching Pydantic schemas.
2. Binary image fixtures are valid images.
3. Batch candidate fixtures are compatible with comparator deterministic scoring.
4. Isolation verification: GreatGenerator is strictly isolated to testing and NOT part of production services.
"""

import io
from PIL import Image
import pytest

from app.schemas import (
    NormalizedAlternative,
    OriginalProduct,
    RetailerListing,
    VisualLabelExtraction,
)
from app.services.product_comparator import (
    generate_recommendation_slots,
    score_alternative_candidate,
)
from app.testing.great_generator import GreatGenerator


def test_great_generator_image_bytes():
    """Verify generated image bytes are syntactically valid JPEG binaries."""
    raw_bytes = GreatGenerator.generate_image_bytes(width=200, height=200, fmt="JPEG")
    assert len(raw_bytes) > 0
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img.verify()
        assert img.format == "JPEG"


def test_great_generator_visual_label_extraction():
    """Verify generated visual label extraction fixture matches schema."""
    ext = GreatGenerator.generate_visual_label_extraction()
    assert isinstance(ext, VisualLabelExtraction)
    assert ext.label_type == "back_of_pack"
    assert ext.is_readable is True
    assert ext.is_complete is True
    assert "Rolled Oats" in ext.ingredient_list
    assert ext.declared_percentages["Rolled Oats"] == 50.0
    assert ext.nutrition_facts["protein_g"] == 12.5


def test_great_generator_original_product():
    """Verify generated original product fixture."""
    prod = GreatGenerator.generate_original_product(brand="YogaBar", product_name="Dark Chocolate Muesli")
    assert isinstance(prod, OriginalProduct)
    assert prod.brand == "YogaBar"
    assert prod.visual_extraction is not None
    assert prod.visual_extraction.extraction_status == "complete"


def test_great_generator_candidate_and_batch():
    """Verify generated candidates are valid and scoreable with comparator."""
    candidates = GreatGenerator.generate_candidate_batch(count=3)
    assert len(candidates) == 3
    for cand in candidates:
        assert isinstance(cand, NormalizedAlternative)
        scored = score_alternative_candidate(cand)
        assert 0.0 <= scored.total_score <= 100.0

    recs = generate_recommendation_slots([score_alternative_candidate(c) for c in candidates])
    assert recs.total_candidates_analyzed == 3
    assert recs.best_overall_value is not None


def test_great_generator_isolation_from_production_services():
    """Verify GreatGenerator is strictly isolated and NOT imported by any production service module."""
    import sys
    import app.services.product_analyzer
    import app.services.product_comparator
    import app.services.image_search
    import app.services.web_search
    import app.services.gemma_service
    import app.main

    # Inspect module globals to ensure GreatGenerator is NOT imported
    prod_modules = [
        app.services.product_analyzer,
        app.services.product_comparator,
        app.services.image_search,
        app.services.web_search,
        app.services.gemma_service,
        app.main,
    ]

    for mod in prod_modules:
        assert "GreatGenerator" not in mod.__dict__, (
            f"Isolation violation: GreatGenerator found in production module {mod.__name__}"
        )
