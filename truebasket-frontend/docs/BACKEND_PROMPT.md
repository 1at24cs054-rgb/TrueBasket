# TrueBasket — Complete Backend & Data Engineering Task

You are the lead backend and data engineer for **TrueBasket**, a hackathon project that uses **Google Gemma 4** through an approved inference method to power food ingredient intelligence and smart grocery price comparison.

The frontend (React + Vite) is already built and tested. Your job is to build the **FastAPI backend** it talks to, plus the **test-data pipeline** (using Great Generator) that lets the backend be tested before real retailer API access is approved.

Do not just provide suggestions or snippets. Make the actual changes, run them, test them, and deliver a working service.

---

## 1. FIRST: Inspect

1. Inspect the existing backend repository (if any): structure, `pyproject.toml` / `requirements.txt`, existing routes, models, tests and README.
2. Read the frontend’s contract: **`truebasket-frontend/docs/BACKEND_API.md`**. That contract is the source of truth — do not change field names, paths or response shapes.
3. Preserve working code. Do not delete unrelated files. Do not commit or push without permission.
4. If the repository is empty, initialise it with the stack below.

After inspecting, proceed with implementation. Do not stop at an audit unless there is a genuine blocker.

## 2. What the frontend already does (do NOT rebuild)

The browser already handles these directly from Open Food Facts and Open Prices:
- product search;
- barcode lookup;
- ingredients, nutrition, additives, Nutri-Score and NOVA;
- alternatives;
- community prices;
- barcode reading from photos;
- the cheapest-store and savings maths.

The backend is needed only for what the browser cannot do safely:

| # | Endpoint | Purpose |
| --- | --- | --- |
| 1 | `POST /api/products/analyze-image` | Read a pack photo with **Gemma 4** when there is no readable barcode |
| 2 | `GET /api/prices` | **Live retailer prices** from authorised sources, with API keys kept server-side |
| 3 | `GET /health` | Liveness check for deployment |

## 3. Technology stack

- Python 3.11+
- FastAPI and Uvicorn
- Pydantic v2 for request/response models
- `httpx` (async) for outbound calls
- Gemma 4 through an **approved inference method** — Google AI Studio, Vertex AI, or a self-hosted runtime such as Ollama or vLLM:
  - provider and model id configurable through environment variables;
  - no hard-coded model names.
- `cachetools` or Redis for caching (in-memory is fine for the hackathon)
- **Great Generator** (`pip install great-generator`) for synthetic test data — tests and local development only
- pytest, pytest-asyncio and `httpx.AsyncClient` for tests
- Ruff for linting

## 4. Required structure

```
truebasket-backend/
  app/
    main.py                 # FastAPI app, CORS, routers, error handlers
    config.py               # Settings from environment (pydantic-settings)
    models.py               # Pydantic models matching BACKEND_API.md exactly
    routes/
      analyze.py            # POST /api/products/analyze-image
      prices.py             # GET /api/prices
      health.py             # GET /health
    gemma/
      client.py             # Provider-agnostic Gemma 4 client (AI Studio / Vertex / Ollama)
      prompts.py            # Label-reading prompt + JSON schema for structured output
      barcode.py            # EAN-13 / EAN-8 / UPC-A checksum validation
    prices/
      base.py               # PriceAdapter interface + Listing model
      amazon.py             # Amazon Product Advertising API adapter
      flipkart.py           # Flipkart Affiliate API adapter
      ondc.py               # ONDC adapter (stub until an integration partner exists)
      registry.py           # Enables adapters whose credentials are present
      cache.py              # TTL cache keyed by (barcode, pincode)
      matching.py           # Barcode-first matching, pack-size normalisation
  data/
    synthetic/
      generate_listings.py  # Great Generator → fixtures in the exact /api/prices format
      generate_labels.py    # Synthetic label-analysis cases for edge-case tests
    fixtures/               # Generated JSON (committed, small)
  tests/
    test_contract.py        # Responses match BACKEND_API.md exactly
    test_prices.py          # Cheapest/matching/caching/edge cases using synthetic listings
    test_analyze.py         # Upload validation, Gemma mocked, barcode checksum
    test_adapters.py        # Adapter parsing with recorded sample payloads
  .env.example
  README.md
  pyproject.toml
```

## 5. Endpoint 1 — `POST /api/products/analyze-image`

### Request (`multipart/form-data`)

| Field | Type | Notes |
| --- | --- | --- |
| `image` | file, required | JPEG / PNG / WebP / HEIC, max 20 MB |
| `budget_inr` | string | Currently always empty — accept and ignore |
| `priority` | string | Currently always `best_value` — accept and ignore |
| `pack_size_preference` | string | Currently always `any` — accept and ignore |
| `avoid_ingredients` | string | JSON-encoded array of strings |

### Behaviour

1. **Validate the upload:**
   - correct type, size and decodable image;
   - convert HEIC to JPEG server-side if needed;
   - downscale very large images before sending to Gemma.
2. Send the image to Gemma 4 with a prompt that asks for **structured JSON only**:
   - barcode digits if visible;
   - brand;
   - product name;
   - pack size;
   - and, optionally, the ingredients text and nutrition table exactly as printed.
3. **Extract only what is visible.** The prompt must forbid guessing. Missing fields must be `null`.
4. **Validate the barcode** with the EAN/UPC check digit. Drop it if invalid, rather than returning a wrong product.
5. Return the response below.

### Response (`200`)

```json
{
  "original_product": {
    "barcode": "8901058851298",
    "brand": "Kellogg's",
    "name": "Muesli Fruit & Nut",
    "quantity": "500 g"
  },
  "label_analysis": {
    "ingredients_text": "Rolled oats (52%), wheat flakes (14%), sugar, …",
    "nutrition_per_100g": {
      "energy_kcal": 395, "protein_g": 9.8, "carbohydrate_g": 68.5,
      "total_sugars_g": 18.2, "added_sugars_g": null, "total_fat_g": 8.9,
      "saturated_fat_g": 2.6, "fibre_g": 7.4, "sodium_mg": 120, "salt_g": null
    },
    "model": "gemma-4 (provider: …)",
    "source": "label"
  }
}
```

- `original_product` is what the frontend uses today:
  - `barcode` → it opens that product;
  - otherwise `brand` + `name` → it runs a search.
- `label_analysis` is optional and **for the next frontend phase**: showing Gemma’s own reading when a product is not in Open Food Facts. Use exactly these nutrient keys, because the frontend already uses them.
- Never invent nutrition values. Use `null` for anything not printed.

### Errors

Use FastAPI’s `{"detail": "…"}` shape:

| Status | Meaning |
| --- | --- |
| 400 | Unreadable image |
| 413 | Too large |
| 422 | Missing field |
| 429 | Rate-limited |
| 502 / 503 | Gemma unavailable |

## 6. Endpoint 2 — `GET /api/prices`

### Query

| Param | Notes |
| --- | --- |
| `barcode` | Always sent; match on it first |
| `query` | Brand + name + pack size, for text-search fallbacks |
| `pincode` | Optional; quick-commerce prices and stock depend on it |

### Response (`200`)

```json
{
  "listings": [
    {
      "retailer_id": "amazon",
      "retailer": "Amazon India",
      "price_inr": 349,
      "mrp_inr": 399,
      "pack_size": { "value": 500, "unit": "g" },
      "in_stock": true,
      "url": "https://www.amazon.in/dp/…",
      "checked_at": "2026-10-23T06:00:00Z"
    }
  ]
}
```

**Field rules:**
- `retailer_id` must be one of the frontend’s ids:
  - `blinkit`, `instamart`, `zepto`, `bigbasket`, `dmart`, `jiomart`, `amazon`, `flipkart`;
  - add new ids only after agreeing with the frontend.
- `pack_size` is **always** normalised to `g` or `ml` (1 kg → 1000 g, 1 L → 1000 ml).
- Omit any field the source did not return. Never fill in guesses.
- No listings → `{"listings": []}` with `200`.

### Behaviour

1. **Adapter registry.** Enable only adapters whose credentials exist in the environment, and log which ones are active at startup.
2. **Run adapters concurrently** with a per-adapter timeout of about 8 s. One adapter failing must not fail the request; log it and continue.
3. **Matching:**
   - barcode / EAN match first;
   - text match only as a fallback;
   - text matches must agree on brand, a normalised product name and pack size within ±5%.
4. **Cache** by `(barcode, pincode)` for 5–10 minutes. The Compare page calls this endpoint about 5 times at once.
5. **Total response time** under about 10 s; the frontend times out at 30 s.

### Price sources (authorised only)

| Adapter | Source | Notes |
| --- | --- | --- |
| `amazon.py` | Amazon Product Advertising API 5.0 | Needs an approved Amazon Associates account and a PA-API application. Follow their licence terms and attribution rules. |
| `flipkart.py` | Flipkart Affiliate API | Product search by keyword or product id. Needs an affiliate id and token. |
| `ondc.py` | ONDC buyer-side integration | Leave as a documented stub until there is an integration partner. |
| Quick-commerce apps | No public API | Do not scrape. Only add an adapter if a partnership or licensed data feed exists. |

**Do not scrape** any site whose terms forbid it. Do not bypass bot protection or CAPTCHAs.

## 7. Great Generator — synthetic test data

Great Generator creates **synthetic** data. Use it **only for tests and local development**. Synthetic listings must **never** be returned by the deployed API, and never shown to users as real prices.

Generate fixtures in the **exact** `/api/prices` listing format:

```python
from great_generator import generate_from_schema

df = generate_from_schema(
    "retailer_id string, retailer string, barcode string, price_inr double, "
    "mrp_inr double, pack_value int, pack_unit string, in_stock boolean, checked_at timestamp",
    rows=1000,
)
```

Post-process with pandas so the data is valid and covers edge cases:
- `retailer_id` drawn only from the eight frontend ids, with matching display names;
- realistic ₹ ranges per pack size, and `mrp_inr >= price_inr` (some rows with no MRP);
- pack sizes in grams/ml, including mismatched sizes for the same barcode (500 g vs 1 kg);
- some rows with missing optional fields, out-of-stock rows, stale `checked_at`, and duplicates;
- valid EAN-13 barcodes (correct check digits), plus a few invalid ones to test rejection.

Write the result to `data/fixtures/listings.json`. Use it in `tests/test_prices.py` through a `FixtureAdapter` that is registered **only inside tests**.

Optional: a local dev server so the frontend can be tested end to end without real APIs.
- Command: `python -m app.main --fixtures`.
- It must refuse to start when `APP_ENV=production`.
- Every retailer name must be prefixed `TEST · `, so it can never be mistaken for real data.

Also generate synthetic label-analysis cases for `test_analyze.py`:
- complete labels;
- partial labels;
- labels without nutrition;
- invalid barcodes.

## 8. Configuration — `.env.example`

```
APP_ENV=development
CORS_ORIGINS=http://localhost:5173

# Gemma 4 (choose one approved provider)
GEMMA_PROVIDER=ai_studio        # ai_studio | vertex | ollama
GEMMA_MODEL=                    # model id from your provider
GEMMA_API_KEY=                  # AI Studio
GOOGLE_CLOUD_PROJECT=           # Vertex
OLLAMA_BASE_URL=http://localhost:11434

# Price adapters (leave empty to disable)
AMAZON_PAAPI_ACCESS_KEY=
AMAZON_PAAPI_SECRET_KEY=
AMAZON_PARTNER_TAG=
FLIPKART_AFFILIATE_ID=
FLIPKART_AFFILIATE_TOKEN=

PRICE_CACHE_TTL_SECONDS=600
MAX_UPLOAD_MB=20
```

Never commit a real `.env`. Never log secrets or full images.

## 9. Security and trust

- **CORS** only for the configured frontend origins.
- **Rate-limit** both endpoints per IP; return `429` with `{"detail": …}`.
- **Validate uploads** by content, not only by file extension. Strip image metadata before sending it to the model.
- Do not store user images after the request, unless explicitly configured for debugging.
- **No medical claims.** Gemma output is limited to what is printed on the label.
- **No invented data**: prices, discounts, stock, URLs, barcodes or nutrition.

## 10. Testing and verification

1. Install dependencies and run `uvicorn app.main:app --reload --port 8000`.
2. Run `ruff check .` and `pytest`, and fix all failures.
3. **Contract test:** responses match `BACKEND_API.md` exactly — field names, types, `{"listings": []}` when empty, and the `{"detail": …}` error shape.
4. **Price tests with synthetic fixtures:**
   - barcode-first matching;
   - rejection of pack-size mismatches;
   - pack-size normalisation (kg → g);
   - a failing adapter doesn’t fail the request;
   - cache hits;
   - concurrency for about 5 simultaneous requests.
5. **Analyze tests** with Gemma mocked:
   - valid image;
   - wrong type;
   - oversized image;
   - an invalid barcode is dropped;
   - `null` for fields not visible;
   - provider error → 502.
6. **Manual end-to-end check with the frontend:**
   - set `VITE_API_URL` and `VITE_PRICE_API_URL` to `http://localhost:8000` in the frontend `.env`;
   - check that “Read the label with Gemma 4” works on the Scan page;
   - check that “Live prices” appear on Where to buy.
7. Confirm no secrets are committed.

Do not claim a test passed unless you actually ran it.

## 11. Definition of done

- [ ] `uvicorn` starts without errors; `/health` returns 200.
- [ ] `POST /api/products/analyze-image` works with a real Gemma 4 call and returns the agreed shape.
- [ ] Barcode check digits are validated.
- [ ] `GET /api/prices` returns the agreed shape, with at least one real adapter wired in when credentials exist, and `{"listings": []}` otherwise.
- [ ] Adapters run concurrently, with timeouts and caching.
- [ ] Great Generator fixtures exist and drive the price tests.
- [ ] Synthetic data cannot reach production.
- [ ] CORS, rate limiting and upload validation are in place.
- [ ] `ruff` and `pytest` pass.
- [ ] README and `.env.example` are present.
- [ ] The frontend works against the backend locally.

## 12. Final report

When finished, report:
1. What was already present.
2. What you implemented.
3. Files created or modified.
4. Commands you ran.
5. Which tests passed or failed.
6. How to start the backend.
7. Which price adapters are active and what credentials each needs.
8. How to regenerate synthetic fixtures.
9. How to connect the frontend.
10. Remaining blockers, such as API approvals still pending.

Do not push commits or open pull requests unless explicitly asked.

**Start by inspecting the repository and `BACKEND_API.md`, then implement.**
