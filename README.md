# 🥑 TrueBasket — AI-Powered Food Intelligence & Smart Grocery Comparison

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-Gemma_4_26B-blueviolet?style=for-the-badge)](https://openrouter.ai)
[![Tavily](https://img.shields.io/badge/Tavily-AI_Search-orange?style=for-the-badge)](https://tavily.com)
[![OpenFoodFacts](https://img.shields.io/badge/Open_Food_Facts-Database-green?style=for-the-badge)](https://world.openfoodfacts.org)

**Know what goes inside. Compare real nutrition. Shop smarter with transparent price-per-100g discovery.**

[Features](#-key-features) • [System Architecture](#-system-architecture) • [Workflow Pipelines](#-workflow-pipelines) • [Use Cases](#-real-world-use-cases) • [API Contracts](#-backend-api-contracts) • [Quickstart](#-quickstart-guide)

</div>

---

## 📖 Overview

Packaged food labels are notorious for misleading marketing: *"High Fibre"* claims hiding 30% refined sugar, *"Natural"* granola baked in palm oil, and *"Zero Added Sugar"* snacks packed with artificial maltodextrin. Furthermore, quick-commerce platforms obfuscate true costs across different pack sizes.

**TrueBasket** solves this with an end-to-end multimodal grocery intelligence assistant:
1. **Multimodal Package Understanding:** Snap or upload any grocery package. **Gemma 4** (`google/gemma-4-26b-a4b-it`) extracts brand names, ingredient panels, declared percentages, and nutritional declarations.
2. **Deep Food Knowledge:** Direct integration with **Open Food Facts** provides instant Nutri-Score (A through E), NOVA food-processing level (1 to 4), and additive safety ratings.
3. **Evidence-Based Healthier Alternatives:** The engine searches for competitor products in the same category, parses their real packaging labels, and ranks alternatives (e.g., *#1 More Fibre*, *#2 Fewer Additives*, *#3 Lower Sugar*).
4. **Transparent Price Intelligence:** Uses live web pricing across quick-commerce stores (Blinkit, Zepto, Instamart, Amazon Fresh) to calculate the real cost per 100g, showing exactly where to buy for the lowest price.

---

## 🌟 Key Features

| Feature | Description |
| :--- | :--- |
| 📸 **Multimodal Label Extraction** | Upload a photo of the front or back of any food package. The vision model analyzes OCR text, barcode numbers, brand, and ingredient percentages. |
| 🔍 **Full-Catalog Search** | Search through 10,000+ Indian and global products by brand, category (muesli, cereals, snacks, dairy), or barcode. |
| 🌿 **Transparent Ingredient Breakdown** | Categorizes every ingredient (main grains, sweetening agents, oils, preservatives, emulsifiers) and flags hidden allergens or palm oil. |
| ⚖️ **Algorithmic Alternative Ranking** | Unbiased health ranking without paid sponsorships. Products are evaluated strictly on sugar, protein, fibre, and NOVA ultra-processing tiers. |
| 💰 **Unit-Price (Per 100g) Comparison** | Normalizes prices across 250g, 500g, and 1kg bags so you never overpay for small convenience packaging. |
| 🛡️ **Custom Dietary Profiles** | Set personal preferences: Avoid Palm Oil, Gluten-Free, Vegan, High Fibre ($\ge 6\text{g}$), or Low Sugar ($\le 5\text{g}$). |

---

## 🏛️ System Architecture

```mermaid
flowchart TB
    subgraph Client["🖥️ TrueBasket Client (React 18 + Vite)"]
        UI[User Interface & Router]
        ScanModule[Camera / File Upload Handler]
        SearchModule[Catalog & Category Filters]
        CompareModule[Product Nutrition & Alternative Tabs]
        PriceModule[Store Price Matrix]
    end

    subgraph Backend["⚡ TrueBasket API Gateway (FastAPI)"]
        API[FastAPI Router]
        VisionSvc["Vision Engine<br/>(OpenRouter Gemma 4 26B)"]
        SearchSvc["Search & Discovery<br/>(Tavily API)"]
        ProxySvc["Catalog Proxy & Fallback<br/>(Open Food Facts)"]
        RankSvc["Scoring & Comparison Engine<br/>(Per-100g Normalizer)"]
    end

    subgraph External["🌐 External AI & Data Providers"]
        OR["OpenRouter AI<br/>google/gemma-4-26b-a4b-it"]
        TAV["Tavily Search Engine"]
        OFF["Open Food Facts API"]
        Stores["Live Retailer Stores<br/>(Blinkit, Zepto, Amazon Fresh)"]
    end

    %% Client to Backend
    ScanModule -->|"POST /api/products/analyze-image"| API
    SearchModule -->|"GET /api/products/search"| API
    CompareModule -->|"GET /api/products/alternatives"| API
    PriceModule -->|"GET /api/prices"| API

    %% Backend Services
    API --> VisionSvc
    API --> SearchSvc
    API --> ProxySvc
    API --> RankSvc

    %% Backend to External
    VisionSvc -->|"Multimodal Base64 Image Payload"| OR
    SearchSvc -->|"Real-time packaging & competitor queries"| TAV
    ProxySvc -->|"Product schema & categories"| OFF
    RankSvc -->|"Live pricing lookup"| Stores
```

---

## 🔄 Workflow Pipelines

### 1. Image Scan & Product Intelligence Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor User as Shopper
    participant UI as TrueBasket Web UI
    participant Backend as FastAPI Backend
    participant Gemma as Gemma 4 (OpenRouter)
    participant OFF as Open Food Facts
    participant Tavily as Tavily Web Search

    User->>UI: Uploads package photo (JPG/PNG/WebP)
    UI->>UI: Check for optical barcode in browser
    alt Barcode recognized locally
        UI->>Backend: GET /api/products/barcode/{barcode}
        Backend->>OFF: Fetch product record
        Backend-->>UI: Return product details
    else No barcode on front of pack
        UI->>Backend: POST /api/products/analyze-image (Multipart)
        Backend->>Backend: Validate MIME type & resize (max 1536px)
        Backend->>Gemma: Multimodal chat completion (base64 image)
        Gemma-->>Backend: JSON: {brand, product_name, ingredients, nutrition}
        Backend->>Tavily: Discover competitor products in same category
        Tavily-->>Backend: Return candidate products & packaging images
        Backend->>Gemma: Extract competitor nutrition & ingredients
        Backend->>Backend: Score & rank alternatives (Fibre, Sugar, Value)
        Backend-->>UI: Return OriginalProduct + Ranked Alternatives
        UI-->>User: Display Product Card & Health Badges
    end
```

### 2. Smart Alternative & Price Comparison Flow

```mermaid
flowchart LR
    A[Selected Product] --> B{Nutritional Audit}
    B -->|Check Sugar & Fibre| C[Filter Competitors]
    B -->|Check Additives & Palm Oil| C
    C --> D[Rank Alternatives]
    D --> E[#1 Highest Fibre]
    D --> F[#2 Minimal Additives]
    D --> G[#3 Best Value]
    
    E & F & G --> H[Fetch Store Listings]
    H --> I[Normalize to ₹ / 100g]
    I --> J[Display Lowest Price Store]
```

---

## 🎯 Real-World Use Cases

```mermaid
mindmap
  root((TrueBasket))
    Shopper in Supermarket
      Take a quick photo of a cereal box
      Instantly see hidden sugar content
      Find if another brand on the shelf has double the fibre
    Diet & Health Conscious
      Filter out palm oil and artificial colours
      Compare NOVA 1 vs NOVA 4 processed alternatives
      Monitor per-serving sodium and saturated fats
    Smart Budget Shopper
      Compare 350g box vs 1kg pouch
      Check real price per 100g
      Discover whether Blinkit, Zepto, or Amazon Fresh has the discount
    Allergy & Intolerance Alert
      Detect hidden gluten, soy, lactose, or nuts
      Highlight cross-contamination warnings from packaging text
```

---

## 🔌 Backend API Contracts

All endpoints are hosted by default on `http://localhost:8000`.

### 1. Health Status
- **Endpoint:** `GET /api/health`
- **Purpose:** Verifies configuration status of OpenRouter Vision, Tavily Search, and Gemma LLM.
- **Sample Response:**
```json
{
  "status": "ok",
  "app_name": "TrueBasket Backend API",
  "version": "0.1.0",
  "services": {
    "vision": {
      "configured": true,
      "status": "ready",
      "model": "google/gemma-4-26b-a4b-it"
    },
    "tavily": {
      "configured": true,
      "status": "ready"
    }
  }
}
```

### 2. Image Analysis
- **Endpoint:** `POST /api/products/analyze-image`
- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `image`: Image file (JPG, PNG, WebP)
  - `priority`: `best_value` | `lower_sugar` | `higher_fibre`
  - `avoid_ingredients`: JSON array (e.g. `["palm oil", "maltodextrin"]`)
- **Sample Response:**
```json
{
  "original_product": {
    "brand": "True Elements",
    "product_name": "Muesli No Added Sugar",
    "name": "Muesli No Added Sugar",
    "net_weight": "1 Kg",
    "ingredient_list": ["Rolled Oats", "Wheat Flakes", "Dried Fruits", "Nuts"],
    "nutrition_facts": {
      "energy_kcal": 425,
      "protein_g": 13.5,
      "sugar_g": 4.2,
      "fibre_g": 10.8
    }
  },
  "recommendations": [
    {
      "rank": 1,
      "reason": "Higher fibre content with 0g added sugar",
      "badge": "More fibre"
    }
  ]
}
```

### 3. Product Search & Catalog Proxy
- **Endpoint:** `GET /api/products/search?q={query}&page=1&page_size=24`
- **Purpose:** Fast, resilient search across Open Food Facts with automatic upstream fallback.

### 4. Live Multi-Store Prices
- **Endpoint:** `GET /api/prices?query={product_name}&barcode={code}`
- **Purpose:** Retrieves verified store listings, packaging size, and unit price per 100g.

---

## 🛠️ Tech Stack & Directory Structure

```
TrueBasket/
├── README.md                      # Complete Project Documentation & System Guides
├── .gitignore                     # Git rules (excludes secrets, venvs, node_modules)
│
├── truebasket-backend/            # ⚡ FastAPI Service
│   ├── app/
│   │   ├── main.py                # FastAPI endpoints & CORS configuration
│   │   ├── config.py              # Environment variable loader
│   │   ├── schemas.py             # Pydantic v2 data models
│   │   └── services/
│   │       ├── openrouter_service.py # Gemma 4 26B vision client (OpenRouter)
│   │       ├── vision_service.py     # Vision dispatch & preprocessing
│   │       ├── product_analyzer.py   # Label parser & health evaluator
│   │       ├── product_comparator.py # Alternative comparison & ranking
│   │       └── web_search.py         # Tavily web search integration
│   ├── tests/                     # Live E2E test suite
│   ├── requirements.txt           # Python dependencies
│   ├── Procfile                   # Cloud deployment command
│   └── render.yaml                # Render platform blueprint
│
└── truebasket-frontend/           # 🖥️ React 18 + Vite Web App
    ├── src/
    │   ├── App.jsx                # Main application & routing
    │   ├── components/            # UI Panels (UploadCard, NutritionPanel, etc.)
    │   ├── pages/                 # HomePage, ScanPage, ProductPage, SearchPage
    │   ├── services/              # API clients (api.js, openFoodFacts.js)
    │   └── index.css              # Custom design system
    ├── package.json               # Frontend dependencies
    └── vite.config.js             # Vite build configuration
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** & `npm`
- An **OpenRouter API Key** (for Gemma 4 Vision)
- A **Tavily API Key** (for web competitor & price discovery)

### 2. Backend Setup
```bash
# 1. Navigate to the backend directory
cd truebasket-backend

# 2. Create and activate a virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and enter your credentials:
# OPENROUTER_API_KEY=sk-or-v1-...
# TAVILY_API_KEY=tvly-...
# AI_VISION_PROVIDER=openrouter
# OPENROUTER_VISION_MODEL=google/gemma-4-26b-a4b-it

# 5. Start the backend server
uvicorn app.main:app --reload --port 8000
```
Backend will be live at `http://127.0.0.1:8000` (API Docs at `http://127.0.0.1:8000/docs`).

### 3. Frontend Setup
```bash
# 1. Open a new terminal and navigate to frontend directory
cd truebasket-frontend

# 2. Install dependencies
npm install

# 3. Create .env file
cp .env.example .env
# Default contents:
# VITE_API_URL=http://localhost:8000

# 4. Start the frontend development server
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Running the Tests

Run the backend verification suite to validate all live integrations:

```bash
cd truebasket-backend

# 1. Test backend health and provider configurations
pytest tests/test_health.py -v

# 2. Test OpenRouter Gemma 4 Vision integration
pytest tests/test_openrouter_vision.py -v

# 3. Test frontend API contracts
pytest tests/test_frontend_integration.py -v
```

---

## 📜 License & Ethics

TrueBasket is open-source under the **MIT License**.
All nutrition scoring and alternative rankings are calculated objectively using public health standards (Nutri-Score, NOVA group, and FSSAI standards). No commercial brands pay for ranking placement.
