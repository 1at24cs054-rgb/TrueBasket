# TrueBasket — Gemma 4 Food Intelligence & Smart Shopping

Welcome to **TrueBasket**, an AI-powered food ingredient intelligence and smart shopping platform built for the AWS Builders Hackathon.

## Repository Layout

- **[`truebasket-backend/`](truebasket-backend/):** FastAPI backend service with Tavily Web Search and Gemma 4 multimodal inference.
- **`truebasket-frontend/`:** React / Next.js frontend (developed in parallel by frontend teammate).

## Quickstart (Backend)

```bash
cd truebasket-backend
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Refer to [truebasket-backend/README.md](truebasket-backend/README.md) for full documentation, API contracts, and smoke testing guides.
