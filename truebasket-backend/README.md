# TrueBasket Backend — Phase 1: Setup & Service Verification

TrueBasket is a **Gemma 4-powered food ingredient intelligence and smart shopping application** built for the MLH × Google Gemma 4 hackathon. Gemma 4 (`gemma-4-26b-a4b-it`) is called through the Gemini API with the `google-genai` SDK.

This repository contains the FastAPI backend responsible for:
1. **Multimodal packaging perception** with Gemma 4 (OCR, ingredients parsing, additive detection).
2. **On-demand web retrieval** using the Tavily Search API (nutrition facts, regulatory warnings, competitor pricing).
3. **Evidence-based synthesis & value recommendations** without maintaining a permanent product database.

---

## 🛠 Technology Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI with Uvicorn (ASGI)
- **Data Validation & Schemas:** Pydantic v2 & Pydantic Settings
- **LLM & Multimodal AI:** Gemma 4 (via official `google-genai` SDK or hosted OpenAI-compatible endpoints)
- **Web Search Engine:** Tavily Search API
- **HTTP Client:** HTTPX (asynchronous)
- **Testing:** Pytest & pytest-asyncio

---

## 📂 Project Structure

```text
truebasket-backend/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Pydantic BaseSettings loading from .env
│   ├── main.py                   # FastAPI application, CORS, lifespan, exception handlers
│   ├── schemas.py                # Pydantic request/response models & API contracts
│   └── services/
│       ├── __init__.py
│       ├── gemma_service.py      # Gemma 4 text and multimodal image inference
│       └── web_search.py         # Asynchronous Tavily Search API client
├── tests/
│   ├── __init__.py
│   ├── test_health.py            # Health check, CORS & security leak tests
│   ├── test_web_search.py        # Tavily parsing, quotas, timeout & error tests
│   └── test_gemma_service.py     # Gemma 4 config inspection & JSON extractor tests
├── .env.example                  # Documented environment template
├── .gitignore                    # Excludes .env, virtualenvs, caches
├── requirements.txt              # Production and testing dependencies
└── README.md                     # Setup, testing, and API contract guide
```

---

## 🚀 Quickstart Guide

### 1. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
cd "c:\Users\Dhanush\OneDrive\ONE DRIVE\OneDrive\Desktop\TrueBasket\truebasket-backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
cd truebasket-backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create your local `.env` file from `.env.example`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` and fill in the values:

```env
# Tavily Search API Key (Get free key: https://tavily.com/)
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx

# Gemma 4 Provider & Model Configuration
# Option A: Google AI Studio (Free Developer Tier)
GEMMA_PROVIDER=google
GEMMA_MODEL=gemma-4-26b-a4b-it
GEMMA_API_KEY=your_google_ai_studio_api_key

# Option B: Hosted OpenAI-compatible endpoint (vLLM / Ollama / AWS Bedrock Proxy)
# GEMMA_PROVIDER=openai_compatible
# GEMMA_API_BASE_URL=http://localhost:11434/v1
# GEMMA_MODEL=gemma-4-12b
# GEMMA_API_KEY=
```

---

## 🏃 Running the Application

Start the local Uvicorn development server:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server is available at:
- **Health Check Endpoint:** [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Testing & Verification

### Running Automated Test Suite

Run all unit and mock tests with pytest:

```powershell
pytest -v
```

### Smoke Test: Tavily Live Search

Run the standalone CLI smoke test to verify live Tavily connectivity:

```powershell
python -m app.services.web_search "muesli ingredients nutrition label India"
```

- When configured with a valid `TAVILY_API_KEY`, it prints retrieved URLs, titles, scores, and content snippets.
- When unconfigured, it clearly reports that the service is unavailable without crashing.

### Smoke Test: Gemma 4 Inference

Run the standalone CLI smoke test to verify Gemma 4 model inference:

```powershell
python -m app.services.gemma_service
```

- When configured, it verifies text generation and structured JSON output.
- When unconfigured, it prints exact missing keys and configuration guides.

---

## 📡 API Contract for Frontend Team

The backend adheres to a strict REST contract with CORS enabled for `http://localhost:3000` and `http://localhost:5173`.

### 1. `GET /api/health`

**Sample Response:**
```json
{
  "status": "degraded",
  "app_name": "TrueBasket Backend API",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-23T05:50:00Z",
  "services": {
    "tavily": {
      "configured": false,
      "status": "missing_configuration",
      "details": "TAVILY_API_KEY is not configured in .env.",
      "provider": null,
      "model": null
    },
    "gemma": {
      "configured": false,
      "status": "missing_configuration",
      "details": "GEMMA_API_KEY is not configured for provider 'google'.",
      "provider": "google",
      "model": "gemma-4-26b-a4b-it"
    }
  }
}
```

### 2. `POST /api/search/smoke-test`

**Request Body:**
```json
{
  "query": "muesli ingredients nutrition label India",
  "max_results": 5,
  "search_depth": "basic"
}
```

**Response (HTTP 200):**
```json
{
  "query": "muesli ingredients nutrition label India",
  "results_count": 5,
  "results": [
    {
      "title": "Healthy Oats & Nut Muesli Ingredients",
      "url": "https://example.com/muesli",
      "content": "Rolled oats, almonds, pumpkin seeds, zero added sugar.",
      "score": 0.94,
      "published_date": "2024-03-15"
    }
  ],
  "response_time_ms": 482.5
}
```

### 3. `POST /api/gemma/smoke-test`

**Request Body:**
```json
{
  "prompt": "Analyze this food item: Muesli with almonds and chia seeds. Return JSON with health_score and pros."
}
```

### 4. `POST /api/products/analyze-image` (Core Phase 2 Feature)

**Summary:** Uploads a food packaging image (muesli / breakfast cereals in India), extracts visible label data with Gemma 4 multimodal perception, performs targeted online web retrieval via Tavily, and synthesizes evidence-based ingredient intelligence.

**Request:** `multipart/form-data`
- `image`: Packaging image file (JPEG, PNG, WEBP, max 10MB) — **Required**
- `budget_inr`: Target budget in INR (e.g. `350`) — *Optional*
- `priority`: `balanced` (default), `lower_sugar`, `higher_fibre`, or `value` — *Optional*
- `pack_size_preference`: `any` (default) or `similar` — *Optional*
- `avoid_ingredients`: JSON array (e.g. `["palm oil", "sugar"]`) or comma-separated string — *Optional*

**Sample Response (HTTP 200):**
```json
{
  "original_product": {
    "brand": "YogaBar",
    "product_name": "Super Muesli",
    "variant": "Fruits, Nuts & Seeds",
    "net_weight": "400g",
    "serving_size": "40g",
    "ingredient_list": [
      "Rolled Oats (50%)",
      "Almonds (12%)",
      "Raisins (8%)",
      "Chia Seeds",
      "Edible Vegetable Oil (Palmolein)",
      "INS 322"
    ],
    "declared_percentages": {
      "Rolled Oats": 50.0,
      "Almonds": 12.0,
      "Raisins": 8.0
    },
    "nutrition_facts": {
      "energy_kcal": 410.0,
      "protein_g": 12.5,
      "total_sugar_g": 9.2,
      "added_sugar_g": 2.0,
      "dietary_fibre_g": 8.5,
      "total_fat_g": 11.0
    },
    "allergen_warnings": [
      "Contains Almonds and Gluten"
    ],
    "barcode": null,
    "fssai_license": null,
    "manufacturer": null,
    "panel_type": "nutrition_and_ingredients",
    "ingredient_panel_missing": false
  },
  "ingredient_analysis": {
    "summary": "Identified product: YogaBar Super Muesli (Fruits, Nuts & Seeds). Base whole grains include Rolled Oats. Formulation includes palm oil / palmolein.",
    "findings": [
      {
        "category": "whole_grains",
        "claim": "Declared Rolled Oats: 50.0%",
        "status": "verified_fact",
        "source_reference": "Product Packaging Ingredient Panel",
        "explanation": "Manufacturer explicitly stamps 50.0% on the product packaging."
      },
      {
        "category": "oils_fats",
        "claim": "Palm oil or palmolein is declared in the ingredients list",
        "status": "verified_fact",
        "source_reference": "Product Packaging Ingredients List",
        "explanation": "Palm oil is commonly used for cluster crunch or shelf stability; consumers monitoring saturated fats should take note."
      }
    ],
    "added_sugars_and_sweeteners": {
      "total_sugar_per_100g": "9.2",
      "added_sugar_per_100g": "2.0",
      "detected_sweeteners": ["Sugar"],
      "has_artificial_sweeteners": false,
      "assessment": "Declared added sugars are limited; natural sugars present from raisins."
    },
    "oils_and_fats": {
      "detected_oils": ["Palmolein"],
      "has_palm_oil": true,
      "has_hydrogenated_fats": false,
      "assessment": "Contains palm oil/palmolein. Consider products using cold-pressed oils or zero added fat."
    },
    "additives_and_preservatives": {
      "preservatives": [],
      "artificial_colours": [],
      "antioxidants": [],
      "emulsifiers_and_stabilizers": ["INS 322 (Lecithin - plant emulsifier)"],
      "flavourings": [],
      "assessment": "Chemical or INS numbers represent standardized functional food additives. INS 322 is a natural plant-based emulsifier."
    },
    "allergens": {
      "declared_allergens": ["Contains Almonds and Gluten"],
      "potential_cross_contamination": [],
      "assessment": "Always review physical packaging before consuming if you have severe anaphylactic allergies."
    },
    "fibre_and_whole_grains": {
      "whole_grains": ["Rolled Oats"],
      "refined_grains": [],
      "dietary_fibre_per_100g": "8.5",
      "assessment": "Whole grains (e.g. rolled oats) provide complex carbohydrates and sustained energy."
    },
    "flags_for_user_avoid_list": [
      {
        "avoided_term": "palmolein",
        "matched_ingredient": "Edible Vegetable Oil (Palmolein)",
        "status": "detected_on_label"
      }
    ]
  },
  "rankings": [
    {
      "candidate": {
        "brand": "YogaBar",
        "product_name": "Super Muesli - 100% Rolled Oats & Nuts",
        "pack_weight_g": 400.0,
        "unit_basis": "g",
        "listed_price_inr": 280.0,
        "price_per_100g": 70.0,
        "nutrition_per_100g": {
          "protein_g": 13.5,
          "fibre_g": 9.2,
          "total_sugar_g": 7.0
        },
        "retailer_listings": [
          {
            "retailer_name": "BigBasket",
            "product_url": "https://www.bigbasket.com/pd/yogabar-super-muesli",
            "listed_price_inr": 280.0,
            "retrieval_timestamp": "2026-10-23T06:30:00Z"
          }
        ],
        "suitability_status": "suitable"
      },
      "rank": 1,
      "total_score": 86.5,
      "ingredient_nutrition_score": 88.0,
      "price_value_score": 78.0,
      "preference_fit_score": 95.0,
      "score_explanation": "High protein (13.5g/100g); High fibre content (9.2g/100g); Unit rate: ₹70.00/100g; Pack size (400g) matches original",
      "trade_offs": []
    }
  ],
  "alternatives": [
    {
      "brand": "YogaBar",
      "product_name": "Super Muesli - 100% Rolled Oats & Nuts",
      "pack_weight_g": 400.0,
      "unit_basis": "g",
      "listed_price_inr": 280.0,
      "price_per_100g": 70.0
    }
  ],
  "recommendations": {
    "best_overall_value": {
      "category": "best_overall_value",
      "category_title": "Best Overall Value",
      "product": { "brand": "YogaBar", "product_name": "Super Muesli", "listed_price_inr": 280.0, "price_per_100g": 70.0 },
      "selection_reason": "Highest balanced score (86.5/100) combining quality nutrition and fair unit price.",
      "evidence_summary": "Verified listings from 1 retailer(s). Best listed price: ₹280.0 for 400g.",
      "comparison_with_original": "Compared to Kellogg's Muesli: offers unit price of ₹70.00/100g. Provides 13.5g protein/100g.",
      "trade_offs": [],
      "missing_or_uncertain_info": [],
      "purchase_links": [
        {
          "retailer_name": "BigBasket",
          "product_url": "https://www.bigbasket.com/pd/yogabar-super-muesli",
          "listed_price_inr": 280.0,
          "retrieval_timestamp": "2026-10-23T06:30:00Z"
        }
      ]
    },
    "cheapest_suitable": {
      "category": "cheapest_suitable",
      "category_title": "Cheapest Suitable Alternative",
      "product": { "brand": "Tata Soulfull", "product_name": "Muesli Crunch", "listed_price_inr": 190.0, "price_per_100g": 47.50 },
      "selection_reason": "Lowest verified unit price at ₹47.50/100g while satisfying all stated ingredient constraints.",
      "evidence_summary": "Priced at ₹190.0 for 400g. Retrieved from verified grocery retailer sources.",
      "comparison_with_original": "Compared to original: offers lower unit cost.",
      "trade_offs": ["Lower protein (9g/100g)"],
      "missing_or_uncertain_info": [],
      "purchase_links": []
    },
    "best_nutrition_match": {
      "category": "best_nutrition_match",
      "category_title": "Best Ingredient & Nutrition Match",
      "product": { "brand": "YogaBar", "product_name": "Super Muesli", "price_per_100g": 70.0 },
      "selection_reason": "Achieved highest ingredient & nutrition rating (88.0/100) aligning with priority.",
      "evidence_summary": "Formulation verified with 13.5g protein and zero excluded additives.",
      "comparison_with_original": "Contains higher whole grains and lower sugar.",
      "trade_offs": [],
      "missing_or_uncertain_info": [],
      "purchase_links": []
    },
    "total_candidates_analyzed": 5,
    "candidates_qualified": 3,
    "candidates_excluded": 2
  },
  "sources": [
    {
      "title": "YogaBar Super Muesli 400g - BigBasket",
      "url": "https://www.bigbasket.com/pd/12345/yogabar-muesli",
      "snippet": "High protein muesli with 50% oats, almonds and seeds.",
      "source_type": "retailer_or_web",
      "score": 0.92,
      "published_date": null
    }
  ],
  "missing_information": [],
  "warnings": [
    "Online web search results are unverified third-party references and must be cross-checked with official physical packaging."
  ],
  "research_status": "complete"
}
```

---

### 5. `POST /api/products/compare` (Standalone Comparison Engine)

**Summary:** Allows client or frontend to provide an original baseline product and a candidate list of alternatives to validate, deterministically score, and return ranking recommendations.

**Request Body (JSON):**
```json
{
  "original_product": {
    "brand": "Kellogg's",
    "product_name": "Muesli Fruit Magic",
    "net_weight": "400g"
  },
  "candidates": [
    {
      "brand": "YogaBar",
      "product_name": "Super Muesli 400g",
      "pack_weight_g": 400.0,
      "unit_basis": "g",
      "listed_price_inr": 290.0,
      "ingredient_list": ["Rolled Oats", "Almonds", "Seeds"],
      "nutrition_per_100g": {
        "protein_g": 14.0,
        "fibre_g": 9.0,
        "total_sugar_g": 8.0
      },
      "retailer_listings": [
        {
          "retailer_name": "BigBasket",
          "product_url": "https://bigbasket.com/pd/yogabar",
          "listed_price_inr": 290.0,
          "retrieval_timestamp": "2026-10-23T06:30:00Z"
        }
      ]
    }
  ],
  "budget_inr": 350.0,
  "priority": "balanced",
  "pack_size_preference": "similar",
  "avoid_ingredients": ["palmolein"]
}
```

---

## ⚖️ Scoring Logic & Deterministic Formulas

The ranking engine in [`app/services/product_comparator.py`](file:///c:/Users/Dhanush/OneDrive/ONE%20DRIVE/OneDrive/Desktop/TrueBasket/truebasket-backend/app/services/product_comparator.py) uses strictly deterministic Python arithmetic (never LLM estimations):

1. **Unit Price Formulas:**
   - Grams: `price_per_100g = (listed_price_inr / pack_weight_g) * 100`
   - Millilitres: `price_per_100ml = (listed_price_inr / pack_volume_ml) * 100`
   - Grams and millilitres are never compared interchangeably.

2. **Serving Nutrition Normalization:**
   - `val_per_100g = (val_per_serving / serving_size_g) * 100`

3. **Hard Exclusions (Applied First):**
   - **Avoid Ingredients:** If any item matches user's `avoid_ingredients`, `suitability_status = "excluded"` (never recommended).
   - **Unknown Ingredients:** If ingredient data is unverified and user specified an avoid term, `suitability_status = "uncertain"` (never assumed safe).
   - **Budget Limit:** If listed price exceeds `budget_inr`, candidate is excluded from Cheapest Suitable.

4. **Multi-Factor Weighted Scoring:**
   - **Ingredient & Nutrition Profile:** **45%** (Fibre density, protein content, sugar levels, zero added sugar bonuses, palm oil penalties).
   - **Price & Value:** **35%** (Normalized unit price per 100g scored relative to Indian breakfast cereal market benchmark: ₹30 to ₹130/100g).
   - **User Preference & Pack Fit:** **20%** (Pack weight delta vs original, budget compliance, explicit priority alignment).

---

## 🔒 Security & Privacy Best Practices

1. `.env` is ignored by `.gitignore` and must never be committed.
2. The `/api/health` endpoint strips and masks all API keys and secrets.
3. Web search results from Tavily are treated as untrusted external content.
4. Latency and quota limits are enforced with timeouts and bounded result sizes.
5. Uploaded product images are processed in-memory and request-scoped; images are never written to permanent disk storage.
