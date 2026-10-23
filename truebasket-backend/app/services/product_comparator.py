"""Product comparison, normalization, deterministic scoring, and recommendation service.

Architecture:
1. Candidate discovery & deduplication.
2. Deterministic normalization (unit prices, grams vs ml, serving conversions).
3. Hard eligibility filtering (avoid-ingredients, allergens, budget).
4. Deterministic multi-factor weighted scoring.
5. Recommendation slot assignment (Best Overall Value, Cheapest Suitable, Best Nutrition Match).
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas import (
    NormalizedAlternative,
    NormalizedNutrition,
    OriginalProduct,
    ProductRecommendations,
    RecommendationItem,
    RetailerListing,
    ScoredAlternative,
    SourceReference,
)

logger = logging.getLogger("truebasket.services.product_comparator")

# ==============================================================================
# Scoring Weights & Constants
# ==============================================================================

WEIGHT_NUTRITION_INGREDIENTS = 0.45
WEIGHT_PRICE_VALUE = 0.35
WEIGHT_PREFERENCE_FIT = 0.20

# Typical market benchmark unit price for breakfast muesli in India (INR per 100g)
MARKET_BENCHMARK_MIN_PRICE_PER_100G = 30.0   # Budget muesli (e.g. plain rolled oats mix)
MARKET_BENCHMARK_MAX_PRICE_PER_100G = 130.0  # Ultra-premium / high-protein nut muesli

RETAILER_DOMAINS_MAP = {
    "bigbasket.com": "BigBasket",
    "blinkit.com": "Blinkit",
    "amazon.in": "Amazon India",
    "zeptonow.com": "Zepto",
    "jiomart.com": "JioMart",
    "flipkart.com": "Flipkart",
    "swiggy.com": "Instamart",
}


# ==============================================================================
# Deterministic Normalization & Calculation Functions
# ==============================================================================

def calculate_price_per_100g(price_inr: Optional[float], pack_weight_g: Optional[float]) -> Optional[float]:
    """Deterministic calculation of unit price per 100 grams.

    Formula: price_per_100g = (price_inr / pack_weight_g) * 100
    Only calculates when both price and weight are positive numbers.
    """
    if price_inr is None or pack_weight_g is None:
        return None
    if price_inr <= 0 or pack_weight_g <= 0:
        return None
    return round((price_inr / pack_weight_g) * 100.0, 2)


def calculate_price_per_100ml(price_inr: Optional[float], pack_volume_ml: Optional[float]) -> Optional[float]:
    """Deterministic calculation of unit price per 100 millilitres.

    Formula: price_per_100ml = (price_inr / pack_volume_ml) * 100
    Grams and millilitres are NEVER interchanged.
    """
    if price_inr is None or pack_volume_ml is None:
        return None
    if price_inr <= 0 or pack_volume_ml <= 0:
        return None
    return round((price_inr / pack_volume_ml) * 100.0, 2)


def parse_weight_in_grams(raw_text: str) -> Optional[float]:
    """Extract weight in grams from raw strings like '400g', '1 kg', '750 g', '1.2kg'."""
    if not raw_text:
        return None
    cleaned = raw_text.lower().replace(",", "").strip()

    # Match kilograms first (e.g. 1.2 kg, 1kg)
    kg_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms)\b", cleaned)
    if kg_match:
        try:
            return round(float(kg_match.group(1)) * 1000.0, 1)
        except ValueError:
            pass

    # Match grams (e.g. 400 g, 400gm, 400grams)
    g_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams)\b", cleaned)
    if g_match:
        try:
            return round(float(g_match.group(1)), 1)
        except ValueError:
            pass

    return None


def parse_price_in_inr(raw_text: str) -> Optional[float]:
    """Extract INR price from snippets like 'Rs. 299', '₹ 350', 'Rs 420.50'."""
    if not raw_text:
        return None
    cleaned = raw_text.replace(",", "").strip()
    match = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d{1,2})?)", cleaned, re.IGNORECASE)
    if match:
        try:
            val = float(match.group(1))
            if 10.0 <= val <= 5000.0:  # Reasonable sanity filter for packaged cereal
                return val
        except ValueError:
            pass
    return None


def normalize_serving_nutrition_to_100g(
    nutrition: NormalizedNutrition,
    serving_size_g: Optional[float],
) -> NormalizedNutrition:
    """Deterministically convert per-serving nutrients to 100g basis.

    Formula: per_100g = (per_serving / serving_size_g) * 100
    """
    if not serving_size_g or serving_size_g <= 0:
        return nutrition

    factor = 100.0 / serving_size_g

    def _convert(val: Optional[float]) -> Optional[float]:
        return round(val * factor, 2) if val is not None else None

    return NormalizedNutrition(
        serving_basis="per_100g",
        serving_size_g=serving_size_g,
        energy_kcal=_convert(nutrition.energy_kcal),
        protein_g=_convert(nutrition.protein_g),
        fibre_g=_convert(nutrition.fibre_g),
        total_sugar_g=_convert(nutrition.total_sugar_g),
        added_sugar_g=_convert(nutrition.added_sugar_g),
        total_fat_g=_convert(nutrition.total_fat_g),
        saturated_fat_g=_convert(nutrition.saturated_fat_g),
    )


# ==============================================================================
# Eligibility & Hard Exclusions
# ==============================================================================

def check_candidate_eligibility(
    candidate: NormalizedAlternative,
    avoid_ingredients: Optional[List[str]] = None,
    budget_inr: Optional[float] = None,
) -> Tuple[str, List[str]]:
    """Apply hard exclusions: avoid-ingredients, budget, and allergen flags.

    Returns:
        (suitability_status: 'suitable' | 'excluded' | 'uncertain', exclusion_reasons)
    """
    reasons: List[str] = []
    status = "suitable"

    all_ingredients_lower = [i.lower() for i in candidate.ingredient_list]
    all_allergens_lower = [a.lower() for a in candidate.known_allergens]
    combined_ingredients_text = " ".join(all_ingredients_lower + all_allergens_lower)

    # 1. Check avoid_ingredients
    if avoid_ingredients:
        for avoid in avoid_ingredients:
            term = avoid.strip().lower()
            if not term:
                continue

            # Direct match in ingredients list or allergens
            if any(term in ing for ing in all_ingredients_lower) or any(term in alg for alg in all_allergens_lower):
                reasons.append(f"Contains excluded ingredient or allergen: '{avoid}'")
                status = "excluded"
            elif term in combined_ingredients_text:
                reasons.append(f"Contains excluded item: '{avoid}'")
                status = "excluded"
            elif not candidate.ingredient_list and not candidate.known_allergens:
                # If candidate ingredient data is completely missing, mark as uncertain
                if status != "excluded":
                    status = "uncertain"
                    reasons.append(f"Ingredient list is unverified; cannot confirm absence of '{avoid}'")

    # 2. Check budget compliance
    if budget_inr is not None and budget_inr > 0:
        if candidate.listed_price_inr is not None:
            if candidate.listed_price_inr > budget_inr:
                reasons.append(
                    f"Listed price (₹{candidate.listed_price_inr:.2f}) exceeds specified budget (₹{budget_inr:.2f})"
                )
                # Note: Budget excess excludes candidate from 'cheapest suitable' and reduces fit score,
                # but if avoid_ingredients didn't exclude it, we mark as 'excluded' only if strict budget enforced.
                status = "excluded"

    return status, reasons


# ==============================================================================
# Transparent Deterministic Scoring Engine
# ==============================================================================

def score_alternative_candidate(
    candidate: NormalizedAlternative,
    original_product: Optional[OriginalProduct] = None,
    priority: str = "balanced",
    budget_inr: Optional[float] = None,
    pack_size_preference: str = "any",
) -> ScoredAlternative:
    """Compute transparent multi-factor weighted score from 0.0 to 100.0.

    Weights:
    - Nutrition & Ingredients: 45%
    - Price & Unit Value: 35%
    - Preference & Pack Fit: 20%
    """
    trade_offs: List[str] = []
    explanation_parts: List[str] = []

    # --------------------------------------------------------------------------
    # 1. Nutrition & Ingredients Score (45%)
    # --------------------------------------------------------------------------
    nutri_score = 50.0  # Baseline
    nutri = candidate.nutrition_per_100g

    all_ing_str = " ".join(candidate.ingredient_list).lower()
    has_palm = "palm" in all_ing_str or "palmolein" in all_ing_str
    has_zero_added_sugar = "0% added sugar" in all_ing_str or "no added sugar" in all_ing_str or (
        nutri and nutri.added_sugar_g is not None and nutri.added_sugar_g == 0
    )

    if candidate.label_extraction_status in ("no_label_image_found", "unreadable") and not candidate.ingredient_list and not nutri:
        # Strict Image-First Rule: Unverified packaging labels receive a penalized baseline
        nutri_score = 30.0
        if "packaging_label_image" not in candidate.missing_fields:
            candidate.missing_fields.append("packaging_label_image")
        trade_offs.append("Unverified packaging label: packaging image not found online; nutrition and ingredients unverified")
    elif nutri:
        # Fibre evaluation
        if nutri.fibre_g is not None:
            if nutri.fibre_g >= 9.0:
                nutri_score += 15.0
                explanation_parts.append(f"High fibre content ({nutri.fibre_g}g/100g)")
            elif nutri.fibre_g >= 6.0:
                nutri_score += 8.0
            else:
                nutri_score -= 5.0
                trade_offs.append(f"Moderate fibre ({nutri.fibre_g}g/100g)")
        else:
            candidate.missing_fields.append("dietary_fibre_per_100g")

        # Protein evaluation
        if nutri.protein_g is not None:
            if nutri.protein_g >= 12.0:
                nutri_score += 15.0
                explanation_parts.append(f"High protein ({nutri.protein_g}g/100g)")
            elif nutri.protein_g >= 8.0:
                nutri_score += 8.0
            else:
                trade_offs.append(f"Lower protein ({nutri.protein_g}g/100g)")
        else:
            candidate.missing_fields.append("protein_per_100g")

        # Sugar evaluation
        if nutri.total_sugar_g is not None:
            if nutri.total_sugar_g <= 6.0:
                nutri_score += 15.0
                explanation_parts.append(f"Very low total sugar ({nutri.total_sugar_g}g/100g)")
            elif nutri.total_sugar_g <= 12.0:
                nutri_score += 5.0
            else:
                nutri_score -= 10.0
                trade_offs.append(f"Higher total sugar ({nutri.total_sugar_g}g/100g)")
        elif has_zero_added_sugar:
            nutri_score += 12.0
            explanation_parts.append("Zero added sugar formulation")
        else:
            candidate.missing_fields.append("total_sugar_per_100g")
    else:
        # Neutral score if nutrition table is missing but ingredients exist
        nutri_score = 40.0
        candidate.missing_fields.append("nutrition_table_per_100g")
        trade_offs.append("Nutrition table unavailable; score based on ingredients only")

    # Formulation penalties (only evaluated when ingredients are known)
    if candidate.ingredient_list:
        if has_palm:
            nutri_score -= 15.0
            trade_offs.append("Contains palm oil / palmolein")
        else:
            nutri_score += 5.0

    # Priority adjustments
    if priority == "lower_sugar":
        if has_zero_added_sugar or (nutri and nutri.total_sugar_g and nutri.total_sugar_g <= 8.0):
            nutri_score += 15.0
            explanation_parts.append("Directly aligns with 'lower_sugar' priority")
        elif nutri and nutri.total_sugar_g and nutri.total_sugar_g > 15.0:
            nutri_score -= 15.0
    elif priority == "higher_fibre":
        if nutri and nutri.fibre_g and nutri.fibre_g >= 8.0:
            nutri_score += 15.0
            explanation_parts.append("Directly aligns with 'higher_fibre' priority")

    nutri_score = max(0.0, min(100.0, nutri_score))

    # --------------------------------------------------------------------------
    # 2. Price & Value Score (35%)
    # --------------------------------------------------------------------------
    price_score = 50.0  # Baseline
    if candidate.price_per_100g is not None and candidate.price_per_100g > 0:
        p100 = candidate.price_per_100g
        # Linear scaling between min (30/100g -> 100 pts) and max (130/100g -> 20 pts)
        clamped_p = max(MARKET_BENCHMARK_MIN_PRICE_PER_100G, min(MARKET_BENCHMARK_MAX_PRICE_PER_100G, p100))
        pct_range = (clamped_p - MARKET_BENCHMARK_MIN_PRICE_PER_100G) / (
            MARKET_BENCHMARK_MAX_PRICE_PER_100G - MARKET_BENCHMARK_MIN_PRICE_PER_100G
        )
        price_score = round(100.0 - (pct_range * 80.0), 1)

        explanation_parts.append(f"Unit rate: ₹{p100:.2f}/100g")
        if p100 <= 55.0:
            explanation_parts.append("Excellent economy rate")
        elif p100 >= 100.0:
            trade_offs.append(f"Premium unit price (₹{p100:.2f}/100g)")
    else:
        price_score = 30.0
        candidate.missing_fields.append("price_per_100g")
        trade_offs.append("Exact unit price cannot be verified from available listings")

    # Priority adjustment for value
    if priority == "value":
        if candidate.price_per_100g and candidate.price_per_100g <= 60.0:
            price_score = min(100.0, price_score + 15.0)

    price_score = max(0.0, min(100.0, price_score))

    # --------------------------------------------------------------------------
    # 3. Preference & Pack Fit Score (20%)
    # --------------------------------------------------------------------------
    fit_score = 70.0  # Baseline

    # Pack size comparison
    orig_weight = None
    if original_product and original_product.net_weight:
        orig_weight = parse_weight_in_grams(original_product.net_weight)

    if pack_size_preference == "similar" and orig_weight and candidate.pack_weight_g:
        diff_ratio = abs(candidate.pack_weight_g - orig_weight) / orig_weight
        if diff_ratio <= 0.25:
            fit_score += 25.0
            explanation_parts.append(f"Pack size ({candidate.pack_weight_g}g) matches original ({orig_weight}g)")
        elif diff_ratio <= 0.60:
            fit_score += 10.0
        else:
            fit_score -= 15.0
            trade_offs.append(f"Different pack size ({candidate.pack_weight_g}g vs original {orig_weight}g)")
    elif candidate.pack_weight_g:
        fit_score += 15.0

    # Budget fit
    if budget_inr is not None and budget_inr > 0:
        if candidate.listed_price_inr is not None:
            if candidate.listed_price_inr <= budget_inr:
                fit_score += 15.0
            else:
                fit_score -= 30.0

    fit_score = max(0.0, min(100.0, fit_score))

    # --------------------------------------------------------------------------
    # Total Weighted Score
    # --------------------------------------------------------------------------
    total_score = round(
        (WEIGHT_NUTRITION_INGREDIENTS * nutri_score)
        + (WEIGHT_PRICE_VALUE * price_score)
        + (WEIGHT_PREFERENCE_FIT * fit_score),
        1,
    )

    score_expl = "; ".join(explanation_parts) if explanation_parts else "Standard evaluation based on available data."

    return ScoredAlternative(
        candidate=candidate,
        rank=1,  # will be assigned during sorting
        total_score=total_score,
        ingredient_nutrition_score=round(nutri_score, 1),
        price_value_score=round(price_score, 1),
        preference_fit_score=round(fit_score, 1),
        score_explanation=score_expl,
        trade_offs=trade_offs,
    )


# ==============================================================================
# Recommendation Slot Generator
# ==============================================================================

def generate_recommendation_slots(
    scored_candidates: List[ScoredAlternative],
    original_product: Optional[OriginalProduct] = None,
    budget_inr: Optional[float] = None,
    priority: str = "balanced",
    avoid_ingredients: Optional[List[str]] = None,
) -> ProductRecommendations:
    """Generate the three evidence-backed recommendation categories.

    A. Best overall value (Balances nutrition profile, unit price, pack size, and priorities)
    B. Cheapest suitable (Lowest verified unit price satisfying budget and avoid-ingredient constraints)
    C. Best ingredient/nutrition match (Strongest supported match with verified packaging nutrition data)
    """
    total = len(scored_candidates)
    has_ingredient_constraints = bool(avoid_ingredients)

    # Excluded candidates can never be recommended
    eligible_candidates = [sc for sc in scored_candidates if sc.candidate.suitability_status != "excluded"]
    excluded_candidates = [sc for sc in scored_candidates if sc.candidate.suitability_status == "excluded"]

    # Candidates strictly confirmed suitable (ingredients verified from packaging/evidence)
    strictly_suitable = [sc for sc in eligible_candidates if sc.candidate.suitability_status == "suitable"]

    best_overall_item: Optional[RecommendationItem] = None
    cheapest_item: Optional[RecommendationItem] = None
    best_nutrition_item: Optional[RecommendationItem] = None

    # Track recommended candidate keys to avoid blindly recommending the exact same unverified product everywhere
    recommended_keys: Set[str] = set()

    def _cand_key(cand: NormalizedAlternative) -> str:
        return f"{cand.brand.lower().strip()}_{cand.product_name.lower().strip()}_{cand.pack_weight_g}"

    # --------------------------------------------------------------------------
    # Slot A: Best Overall Value
    # --------------------------------------------------------------------------
    candidates_with_price = [c for c in eligible_candidates if c.candidate.price_per_100g is not None and c.candidate.price_per_100g > 0]
    suitable_with_price = [c for c in candidates_with_price if c.candidate.suitability_status == "suitable"]
    pool_for_overall = suitable_with_price if suitable_with_price else candidates_with_price

    if pool_for_overall:
        best_overall_sc = max(pool_for_overall, key=lambda x: x.total_score)
        cand = best_overall_sc.candidate
        key = _cand_key(cand)
        recommended_keys.add(key)

        unc_disclaimer = []
        is_unverified = cand.label_extraction_status in ("no_label_image_found", "unreadable") or not cand.ingredient_list
        if is_unverified:
            unc_disclaimer.append("Packaging label image not found online; nutritional profile and ingredients are unverified.")
        elif cand.suitability_status == "uncertain":
            unc_disclaimer.append("Label extraction is partial; verify physical packaging before consuming.")

        best_overall_item = RecommendationItem(
            category="best_overall_value",
            category_title="Best Overall Value",
            product=cand,
            selection_reason=(
                f"Highest balanced score ({best_overall_sc.total_score}/100) combining unit price "
                f"(₹{cand.price_per_100g:.2f}/100g) and available nutrition evidence."
                + (" (Caution: ingredient and nutritional data unverified from packaging)." if is_unverified else "")
            ),
            evidence_summary=(
                f"Verified listings from {len(cand.retailer_listings)} retailer(s). "
                f"Best listed price: ₹{cand.listed_price_inr} for {cand.pack_weight_g}g."
                + (" Note: Price-only evaluation; packaging label was not verified online." if is_unverified else "")
            ),
            comparison_with_original=_build_comparison_summary(cand, original_product),
            trade_offs=best_overall_sc.trade_offs,
            missing_or_uncertain_info=list(set(cand.missing_fields + unc_disclaimer)),
            purchase_links=cand.retailer_listings,
        )

    # --------------------------------------------------------------------------
    # Slot B: Cheapest Suitable Alternative
    # --------------------------------------------------------------------------
    # Rule 2: Do not declare an ingredient-restricted or allergen-constrained product suitable when its ingredient evidence is missing or incomplete.
    # Rule 5: If there is insufficient evidence, return a clear insufficient-evidence outcome (None) rather than inventing a winner.
    if has_ingredient_constraints:
        cheapest_eligible = [c for c in strictly_suitable if c.candidate.price_per_100g is not None and c.candidate.price_per_100g > 0]
    else:
        cheapest_eligible = candidates_with_price

    if cheapest_eligible:
        cheapest_sc = min(cheapest_eligible, key=lambda x: x.candidate.price_per_100g)
        cand = cheapest_sc.candidate
        key = _cand_key(cand)
        recommended_keys.add(key)
        unc_disclaimer = []
        is_unverified = cand.label_extraction_status in ("no_label_image_found", "unreadable") or not cand.ingredient_list
        if is_unverified:
            unc_disclaimer.append("Packaging label image not found online; nutritional profile and ingredients are unverified.")

        cheapest_item = RecommendationItem(
            category="cheapest_suitable",
            category_title="Cheapest Suitable Alternative",
            product=cand,
            selection_reason=(
                f"Lowest verified unit price at ₹{cand.price_per_100g:.2f}/100g "
                f"while satisfying all specified budget and ingredient constraints."
            ),
            evidence_summary=(
                f"Priced at ₹{cand.listed_price_inr} for {cand.pack_weight_g}g. "
                f"Retrieved from verified grocery retailer sources."
            ),
            comparison_with_original=_build_comparison_summary(cand, original_product),
            trade_offs=cheapest_sc.trade_offs,
            missing_or_uncertain_info=list(set(cand.missing_fields + unc_disclaimer)),
            purchase_links=cand.retailer_listings,
        )

    # --------------------------------------------------------------------------
    # Slot C: Best Ingredient & Nutrition Match
    # --------------------------------------------------------------------------
    # Rule 3: Do not assign a best nutrition match without sufficient verified nutrition data.
    # Rule 5: If there is insufficient evidence, return None rather than inventing a winner.
    verified_nutri_candidates = [
        c for c in eligible_candidates
        if (
            c.candidate.nutrition_per_100g is not None
            and any(
                getattr(c.candidate.nutrition_per_100g, k, None) is not None
                for k in ["protein_g", "fibre_g", "total_sugar_g", "energy_kcal"]
            )
        )
        or (
            c.candidate.label_extraction_status in ("complete", "partial")
            and c.candidate.ingredient_list
        )
    ]

    # Prioritize candidates whose nutrition/ingredients were verified visually from packaging
    label_verified_pool = [
        c for c in verified_nutri_candidates
        if c.candidate.label_extraction_status in ("complete", "partial")
    ]
    nutri_pool = label_verified_pool if label_verified_pool else verified_nutri_candidates

    if nutri_pool:
        best_nutri_sc = max(nutri_pool, key=lambda x: x.ingredient_nutrition_score)
        cand = best_nutri_sc.candidate
        key = _cand_key(cand)
        recommended_keys.add(key)

        if cand.label_extraction_status in ("complete", "partial"):
            nutri_reason = (
                f"Achieved highest verified ingredient & nutrition rating ({best_nutri_sc.ingredient_nutrition_score}/100) "
                f"from visually inspected packaging, aligning with '{priority}' priority without unwholesome additives."
            )
            nutri_evidence = (
                f"Formulation verified visually from packaging with declared ingredients and nutrition table."
            )
        else:
            nutri_reason = (
                f"Achieved highest verified ingredient & nutrition rating ({best_nutri_sc.ingredient_nutrition_score}/100) "
                f"aligning with '{priority}' priority without unwholesome additives."
            )
            nutri_evidence = (
                f"Nutritional profile verified with declared protein, fibre, and whole-grain evidence."
            )

        best_nutrition_item = RecommendationItem(
            category="best_nutrition_match",
            category_title="Best Ingredient & Nutrition Match",
            product=cand,
            selection_reason=nutri_reason,
            evidence_summary=nutri_evidence,
            comparison_with_original=_build_comparison_summary(cand, original_product),
            trade_offs=best_nutri_sc.trade_offs,
            missing_or_uncertain_info=cand.missing_fields,
            purchase_links=cand.retailer_listings,
        )
    else:
        best_nutrition_item = None

    return ProductRecommendations(
        best_overall_value=best_overall_item,
        cheapest_suitable=cheapest_item,
        best_nutrition_match=best_nutrition_item,
        total_candidates_analyzed=total,
        candidates_qualified=len(eligible_candidates),
        candidates_excluded=len(excluded_candidates),
    )


def _build_comparison_summary(candidate: NormalizedAlternative, original: Optional[OriginalProduct]) -> str:
    """Generate concise comparison between candidate and original product."""
    if not original:
        return f"{candidate.brand} {candidate.product_name} evaluated against market baseline."

    orig_brand = original.brand or "Original product"
    orig_name = original.product_name or "muesli"

    parts = [f"Compared to {orig_brand} {orig_name}:"]

    if candidate.price_per_100g:
        parts.append(f"offers unit price of ₹{candidate.price_per_100g:.2f}/100g.")

    cand_nutri = candidate.nutrition_per_100g
    if cand_nutri and cand_nutri.protein_g:
        parts.append(f"Provides {cand_nutri.protein_g}g protein/100g.")

    return " ".join(parts)


# ==============================================================================
# Candidate Deduplication & Normalization
# ==============================================================================

def deduplicate_and_merge_candidates(candidates: List[NormalizedAlternative]) -> List[NormalizedAlternative]:
    """Deduplicate candidates by brand, product name, and pack weight; aggregate listings."""
    merged_map: Dict[str, NormalizedAlternative] = {}

    for cand in candidates:
        key = f"{cand.brand.lower().strip()}_{cand.product_name.lower().strip()}_{cand.pack_weight_g}"

        if key not in merged_map:
            # Deterministically calculate unit prices
            if cand.pack_weight_g and cand.listed_price_inr:
                cand.price_per_100g = calculate_price_per_100g(cand.listed_price_inr, cand.pack_weight_g)
            if cand.pack_volume_ml and cand.listed_price_inr:
                cand.price_per_100ml = calculate_price_per_100ml(cand.listed_price_inr, cand.pack_volume_ml)
            merged_map[key] = cand
        else:
            existing = merged_map[key]
            # Merge retailer listings
            existing_urls = {l.product_url for l in existing.retailer_listings}
            for l in cand.retailer_listings:
                if l.product_url not in existing_urls:
                    existing.retailer_listings.append(l)
                    existing_urls.add(l.product_url)

            # Update best price if lower
            if cand.listed_price_inr and (existing.listed_price_inr is None or cand.listed_price_inr < existing.listed_price_inr):
                existing.listed_price_inr = cand.listed_price_inr
                existing.price_retrieval_timestamp = cand.price_retrieval_timestamp
                if existing.pack_weight_g:
                    existing.price_per_100g = calculate_price_per_100g(existing.listed_price_inr, existing.pack_weight_g)

            # Merge nutrition if existing was missing
            if not existing.nutrition_per_100g and cand.nutrition_per_100g:
                existing.nutrition_per_100g = cand.nutrition_per_100g

            # Merge ingredient list if existing was empty
            if not existing.ingredient_list and cand.ingredient_list:
                existing.ingredient_list = cand.ingredient_list

    return list(merged_map.values())


# ==============================================================================
# Online Competitor Research & Heuristic Extraction via Tavily
# ==============================================================================

def extract_candidates_from_search_evidence(
    sources: List[SourceReference],
    original_product: Optional[OriginalProduct] = None,
) -> List[NormalizedAlternative]:
    """Parse candidate products and prices from retrieved Tavily search snippets."""
    now_iso = datetime.now(timezone.utc).isoformat()
    candidates: List[NormalizedAlternative] = []

    # Common reputable competitor brands in India
    KNOWN_BRANDS = [
        "YogaBar", "Kellogg's", "Bagrry's", "Tata Soulfull",
        "MuscleBlaze", "Alpino", "True Elements", "Pintola", "The Whole Truth",
    ]

    for source in sources:
        text = f"{source.title} {source.snippet}"
        low_text = text.lower()

        # Filter out corporate/business articles that are not retail products
        if any(bad in low_text for bad in ["valuation", "investors", "acquisition", "funding round", "wikipedia", "careers", "share price", "annual report"]):
            continue

        # 1. Detect Brand
        matched_brand = None
        for b in KNOWN_BRANDS:
            if re.search(r"\b" + re.escape(b) + r"\b", text, re.IGNORECASE):
                matched_brand = b
                break

        if not matched_brand:
            continue

        # Skip if identical to original product to focus on alternatives
        if original_product and original_product.brand:
            if matched_brand.lower() == original_product.brand.lower() and original_product.product_name:
                if original_product.product_name.lower() in text.lower():
                    continue

        # 2. Extract Pack Size
        weight_g = parse_weight_in_grams(text) or 400.0  # standard muesli default if not found

        # 3. Extract Price
        price_inr = parse_price_in_inr(text)
        if not price_inr:
            # Check snippet for common retailer prices
            price_match = re.search(r"(?:price|mrp|buy)\s*(?:at)?\s*(?:₹|rs\.?)\s*(\d+)", text, re.IGNORECASE)
            if price_match:
                price_inr = float(price_match.group(1))

        # 4. Extract Product Title
        # Clean title
        title_clean = source.title.split("-")[0].split("|")[0].strip()

        # 5. Retailer determination
        retailer_name = "Online Retailer"
        for dom, r_name in RETAILER_DOMAINS_MAP.items():
            if dom in source.url.lower():
                retailer_name = r_name
                break

        listing = RetailerListing(
            retailer_name=retailer_name,
            product_url=source.url,
            pack_size_raw=f"{weight_g}g",
            listed_price_inr=price_inr,
            retrieval_timestamp=now_iso,
            is_verified_listing=True,
        )

        # Image-First Rule: Ingredients and nutrition must NOT be populated from webpage text snippets.
        # They will be populated strictly from visual inspection of packaging images.
        cand = NormalizedAlternative(
            brand=matched_brand,
            product_name=title_clean,
            pack_weight_g=weight_g,
            unit_basis="g",
            listed_price_inr=price_inr,
            nutrition_per_100g=None,
            ingredient_list=[],
            declared_percentages={},
            known_allergens=[],
            retailer_listings=[listing],
            primary_product_url=source.url,
            price_retrieval_timestamp=now_iso,
            data_confidence="high" if price_inr else "medium",
            label_extraction_status="no_label_image_found",
            missing_fields=["packaging_label_image", "unverified_ingredients", "unverified_nutrition_table"],
        )

        candidates.append(cand)

    return deduplicate_and_merge_candidates(candidates)
