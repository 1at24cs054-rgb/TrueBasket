# TrueBasket — Backend API contract

**For:** the backend developer (FastAPI).
**From:** the frontend. The frontend calls exactly the endpoints below — nothing else.

The website already works without a backend: product data comes from Open Food Facts and community prices from Open Prices, both straight from the browser. The backend adds two things the browser can’t do safely on its own:

| # | Endpoint | Purpose | Frontend switch |
| --- | --- | --- | --- |
| 1 | `POST /api/products/analyze-image` | Read a pack photo with **Gemma 4** when there’s no readable barcode | `VITE_API_URL` |
| 2 | `GET /api/prices` | **Live prices** from retailer APIs (Amazon PA-API, Flipkart Affiliate, ONDC, partners) | `VITE_PRICE_API_URL` |

Both can run on the same server, e.g. `http://localhost:8000`. A machine-readable version of this contract is in [`openapi.yaml`](openapi.yaml).

---

## Setup checklist

1. **CORS** — allow the frontend’s origin:

   ```python
   from fastapi.middleware.cors import CORSMiddleware

   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:5173", "https://<your-deployed-frontend>"],
       allow_methods=["GET", "POST", "OPTIONS"],
       allow_headers=["*"],
   )
   ```

2. **Secrets stay on the server.** Gemma / inference keys and retailer API keys go in the backend’s environment only. The frontend never sends or receives them.

3. **Errors** use FastAPI’s normal shape — a non-2xx status with `{"detail": "Human-readable message"}`. The frontend shows `detail` to the user, and also understands FastAPI’s validation-error list.

4. **Rate limiting** — return **429** when busy. The frontend shows a “limiting requests, try again in a minute” message.

5. **Timeouts** — the frontend waits up to:
   - **90 s** for image analysis;
   - **30 s** for prices.

---

## 1 · `POST /api/products/analyze-image`

Called from the Scan page **only** when the user’s photo has no readable barcode and they tap **“Read the label with Gemma 4 instead”**.

### Request — `multipart/form-data`

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `image` | file | `label.jpg` | JPEG, PNG, WebP or HEIC, up to 20 MB |
| `budget_inr` | string | `""` | Currently always empty — accept and ignore |
| `priority` | string | `"best_value"` | Currently always `best_value` — accept and ignore |
| `pack_size_preference` | string | `"any"` | Currently always `any` — accept and ignore |
| `avoid_ingredients` | string (JSON array) | `"[]"` | JSON-encoded list of strings |

The three “accept and ignore” fields are kept so the original agreed contract doesn’t break.

```python
from fastapi import FastAPI, File, Form, UploadFile
import json

@app.post("/api/products/analyze-image")
async def analyze_image(
    image: UploadFile = File(...),
    budget_inr: str = Form(""),
    priority: str = Form("best_value"),
    pack_size_preference: str = Form("any"),
    avoid_ingredients: str = Form("[]"),
):
    avoid = json.loads(avoid_ingredients or "[]")
    # 1. Run Gemma 4 on the image: read barcode digits, brand, product name, pack size.
    # 2. Return what was identified (see below).
```

### Response — `200 OK`

The frontend only needs to know **which product** it is. Return a barcode when you can read one:

```json
{ "original_product": { "barcode": "8901058851298" } }
```

Otherwise return brand and name (and size if visible):

```json
{ "original_product": { "brand": "Kellogg's", "name": "Muesli Fruit & Nut", "quantity": "500 g" } }
```

What the frontend does with the response:
- **`barcode`** (8–14 digits) → opens that product page.
- **`brand` + `name`** → runs a search with them; the user picks the right size from the results.
- **Neither field** → shows “no product could be identified”.

Extra fields are allowed and ignored for now, e.g. Gemma’s `ingredients`, `nutrition` or `confidence`. This leaves room to show Gemma’s own analysis later.

### Errors

| Status | When | Example body |
| --- | --- | --- |
| 400 | Not an image / unreadable | `{"detail": "The file is not a readable image."}` |
| 413 | Too large | `{"detail": "Image must be under 20 MB."}` |
| 422 | Missing `image` | FastAPI default |
| 429 | Busy | `{"detail": "Too many requests, try again shortly."}` |
| 502/503 | Gemma unavailable | `{"detail": "Label reader is temporarily unavailable."}` |

---

## 2 · `GET /api/prices`

Called from:
- **Where to buy** — once for the product on screen;
- **Compare alternatives** — once each for the product and up to four ranked alternatives (about 5 calls).

The results are used to pick the **cheapest store per 100 g** and to show **“You could save ₹X per 100 g”**.

### Query parameters

| Param | Example | Notes |
| --- | --- | --- |
| `barcode` | `8901058851298` | Always sent. **Match on this first.** |
| `query` | `Kellogg's Muesli Fruit & Nut 500 g` | Brand + name + size, for retailers you must search by text |
| `pincode` | `560001` | Sent if the user set one. Quick-commerce prices and stock depend on it. |

### Response — `200 OK`

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
      "url": "https://www.amazon.in/dp/XXXXXXXX",
      "checked_at": "2026-10-23T06:00:00Z"
    }
  ]
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `retailer` | yes | Display name |
| `price_inr` | yes | Number, the selling price for this pack. Listings without it are dropped. |
| `retailer_id` | recommended | Use the frontend’s ids: `blinkit`, `instamart`, `zepto`, `bigbasket`, `dmart`, `jiomart`, `amazon`, `flipkart` |
| `pack_size` | **strongly recommended** | `{ "value": number, "unit": "g" \| "ml" }` (kg → g, L → ml). Without it, per-100 g comparison falls back to the product’s own size. |
| `mrp_inr` | optional | Shown struck through when higher than `price_inr` |
| `in_stock` | optional | `true` / `false`; omit if unknown |
| `url` | optional | Product page link for the “Buy on …” button |
| `checked_at` | recommended | ISO-8601 time the price was fetched |

- **No listings found:** return `{"listings": []}` with `200`. The frontend shows “No live listings were returned”.
- **Errors:** use the same shape as above. A failure only hides the live-price section; the rest of the page keeps working.

### Rules for price adapters

1. **Never invent** a price, discount, stock status or URL. If a source doesn’t return it, leave it out.
2. **Match by barcode first.** Text search only as a fallback, and make sure the pack size matches.
3. **Always return `pack_size`.** Without it, comparing a 500 g pack against a 1 kg pack is meaningless.
4. **Cache** results per `(barcode, pincode)` for a few minutes. The Compare page makes about 5 calls at once.
5. **Only use sources you have the right to use:**
   - **Amazon** — Product Advertising API (needs an approved Associates account);
   - **Flipkart** — Affiliate API;
   - **ONDC** — through a buyer-side integration;
   - **direct partnerships**.
   Don’t scrape sites whose terms forbid it.

Suggested backend layout:

```
backend/
  app/main.py              # FastAPI app, CORS, routes
  app/gemma.py             # label reading
  app/prices/
    base.py                # class PriceAdapter: async def fetch(barcode, query, pincode) -> list[Listing]
    amazon.py              # PA-API
    flipkart.py            # Affiliate API
    cache.py
  .env                     # GEMMA_*, AMAZON_*, FLIPKART_* — never committed
```

---

## Testing the backend against the frontend

```bash
# Prices
curl "http://localhost:8000/api/prices?barcode=8901058851298&query=muesli%20500%20g&pincode=560001"

# Label reading
curl -F "image=@label.jpg" -F "budget_inr=" -F "priority=best_value" \
     -F "pack_size_preference=any" -F 'avoid_ingredients=[]' \
     http://localhost:8000/api/products/analyze-image
```

Then in the frontend’s `.env`:

```
VITE_API_URL=http://localhost:8000
VITE_PRICE_API_URL=http://localhost:8000
```

Restart `npm run dev` after changing `.env`. You’ll see:
- **Read the label with Gemma 4** on the Scan page when a photo has no barcode;
- a **Live prices** section on Where to buy;
- live prices used on Compare alternatives.

## What the backend does NOT need to do

The frontend already handles these directly:
- product search;
- barcode lookup;
- ingredients, nutrition, additives, Nutri-Score and alternatives (Open Food Facts);
- community prices (Open Prices);
- barcode reading from photos;
- the cheapest-store and savings maths.
