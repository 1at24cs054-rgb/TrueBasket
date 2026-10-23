# 🥑 TrueBasket Model Context Protocol (MCP) Server

[![MCP](https://img.shields.io/badge/MCP-2.3.0-blue?style=for-the-badge&logo=anthropic)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Connected-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamable_HTTP](https://img.shields.io/badge/Transport-Streamable_HTTP-success?style=for-the-badge)](https://modelcontextprotocol.io/)

The **TrueBasket MCP Server** exposes TrueBasket's food product intelligence, Gemma 4 packaging vision extraction, Open Food Facts database integration, ingredient preference auditing, and multi-store price discovery as standardized Model Context Protocol (MCP) tools for AI assistants (such as Claude Desktop, Cursor, Antigravity, and custom LLM agents).

---

## 🛠️ Registered MCP Tools

| Tool | Parameters | Description | Backend Endpoint Called |
| :--- | :--- | :--- | :--- |
| `search_products` | `query` *(string)*, `page_size` *(int, default: 10)* | Search catalog by brand, product name, or category. Returns Nutri-Score, NOVA group, pack size, and photos. | `GET /api/products/search` |
| `get_product_details` | `barcode` *(string)* | Retrieve full nutrition table (per 100g & per serving), explicit ingredients, allergens, additives, and completeness rating. | `GET /api/products/barcode/{barcode}` |
| `analyze_food_image` | `image_base64` *(string)* or `image_url` *(string)*, `priority` *(string)*, `avoid_ingredients` *(list)* | Multimodal label understanding via Gemma 4 (`google/gemma-4-26b-a4b-it`). Identifies pack, extracts ingredients & nutrition, and suggests alternatives. | `POST /api/products/analyze-image` |
| `compare_alternatives` | `product_identifier` *(string)*, `budget` *(float)*, `excluded_ingredients` *(list)*, `priority` *(string)* | Discovers and ranks genuinely healthier alternative products with mathematical justification (lower sugar, higher fibre, fewer additives). | `GET /api/products/alternatives` |
| `find_product_prices` | `product_name` *(string)*, `barcode` *(string)*, `pincode` *(string)*, `pack_size` *(string)* | Retrieves live store listings (Blinkit, Zepto, Amazon Fresh, Instamart) and computes unit cost per 100g. | `GET /api/prices` |
| `check_ingredient_preferences` | `excluded_ingredients` *(list)*, `product_identifier` *(string)*, `ingredients` *(list)* | Audits product ingredients against user dietary exclusions and allergies (palm oil, sugars, gluten, dairy, artificial sweeteners) with synonym matching. | `GET /api/products/barcode/{barcode}` (if needed) |

---

## 🔒 Security & Guardrails

- **Zero API Key Leaks:** API keys and sensitive tokens (`sk-or-v1-...`, `tvly-...`, `Bearer ...`) are automatically scrubbed and redacted from all logs and tool error responses.
- **SSRF Defense:** When `image_url` is supplied, the server parses the URL, resolves the DNS hostname, and explicitly blocks all private, loopback, link-local, and cloud metadata IP ranges (`127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`, `::1`).
- **File Validation:** Restricts image payload sizes to $\le 20\text{ MB}$ and validates image header magic bytes via Pillow (JPEG, PNG, WebP only).
- **Bearer Authentication:** For remote deployments, setting `MCP_AUTH_TOKEN` activates Starlette authentication middleware, requiring an `Authorization: Bearer <token>` header for all MCP requests.

---

## 🚀 Local Setup & Installation (Windows PowerShell)

### 1. Create and Activate Virtual Environment
```powershell
cd c:\Users\Dhanush\OneDrive\ONE DRIVE\OneDrive\Desktop\TrueBasket\truebasket-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```powershell
copy .env.example .env
```
Default `.env` configuration:
```ini
TRUEBASKET_API_BASE_URL=http://127.0.0.1:8000
MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_TRANSPORT=streamable-http
MCP_STREAMABLE_HTTP_PATH=/mcp
BACKEND_TIMEOUT_SECONDS=180
LOG_LEVEL=INFO
```

### 4. Ensure the TrueBasket Backend Is Running
In another terminal:
```powershell
cd ..\truebasket-backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. Start the TrueBasket MCP Server
- **For Streamable HTTP (Remote / Web AI clients):**
  ```powershell
  python server.py --transport streamable-http --port 8001
  ```
  Health check is accessible at `http://127.0.0.1:8001/health`.
  MCP endpoint is available at `http://127.0.0.1:8001/mcp`.

- **For Stdio (Local Desktop AI clients like Claude Desktop):**
  ```powershell
  python server.py --transport stdio
  ```

---

## 🔌 Connecting to MCP Clients

### 1. Claude Desktop Configuration (`claude_desktop_config.json`)
For local stdio connection:
```json
{
  "mcpServers": {
    "truebasket": {
      "command": "c:\\Users\\Dhanush\\OneDrive\\ONE DRIVE\\OneDrive\\Desktop\\TrueBasket\\truebasket-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "c:\\Users\\Dhanush\\OneDrive\\ONE DRIVE\\OneDrive\\Desktop\\TrueBasket\\truebasket-mcp\\server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "TRUEBASKET_API_BASE_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

### 2. Streamable HTTP Client / MCP Inspector
Connect using the official MCP Inspector or any HTTP-compatible MCP client:
- **Server URL:** `http://127.0.0.1:8001/mcp`
- **Transport:** `Streamable HTTP`
- **Headers (if `MCP_AUTH_TOKEN` is configured):**
  `Authorization: Bearer <your-secret-mcp-token>`

---

## 🧪 Automated Testing

### Run Unit Tests (Mocked Backend & Security Boundaries)
```powershell
pytest tests/test_unit_mcp.py -v
```
*Validates schema validation, tool registration, SSRF IP blocking, secret redaction, and error formats.*

### Run Live Integration Tests (Against Live Backend)
```powershell
pytest tests/test_live_mcp.py -v
```
*Validates real communication with TrueBasket backend: search, barcode lookup, alternatives ranking, multi-store pricing, and multimodal vision analysis.*

---

## 🌐 Remote Deployment & Production

1. **Deploy Behind Reverse Proxy (Nginx / Caddy / Cloudflare):**
   - Terminate SSL/TLS at reverse proxy for HTTPS.
   - Forward `/mcp` traffic to internal port `8001`.
2. **Set Security Environment Variables:**
   ```bash
   MCP_HOST=0.0.0.0
   MCP_PORT=8001
   MCP_AUTH_TOKEN=your-random-64-char-hex-token
   TRUEBASKET_API_BASE_URL=https://api.yourdomain.com
   ```
3. **Health & Readiness Check:**
   `GET https://mcp.yourdomain.com/health` returns `HTTP 200 OK` with registered tool names and server status.
