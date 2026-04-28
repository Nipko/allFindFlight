# AllfindFlight

Búsqueda inteligente de vuelos baratos: combina APIs y scraping directo a aerolíneas, con expansión automática a aeropuertos cercanos, transporte terrestre y rutas creativas (self-transfer, hidden-city, stopover-as-destination).

## Stack

- **Backend:** Python 3.11 + FastAPI + Celery + SQLAlchemy
- **Frontend:** Next.js (App Router)
- **Infra:** Postgres + Redis + Docker Compose
- **Scraping:** `fast-flights` (Google Flights), `curl_cffi`, `camoufox`
- **Geo:** OurAirports + H3 (Uber)

## Quickstart

```bash
# 1. Levantar infra
docker compose -f infra/docker-compose.yml up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -e .
python -m app.scripts.seed_airports
uvicorn app.main:app --reload

# 3. Worker (otra terminal)
celery -A app.workers.celery_app worker -l info -P solo  # -P solo en Windows

# 4. Frontend
cd frontend
npm install
npm run dev
```

## Despliegue

Producción en VPS Ubuntu nativo + Cloudflare Tunnel: ver [`infra/DEPLOY.md`](infra/DEPLOY.md).
Imágenes se publican automáticamente a GHCR vía GitHub Actions en cada push a `main`.

## Estructura

```
backend/app/
├── api/          # FastAPI routers
├── workers/      # Celery tasks
├── adapters/     # Interfaz uniforme de fuentes (Google Flights, Ryanair, ...)
├── scrapers/     # Lógica de scraping específica
├── aggregator/   # Mezcla, dedup, ranking
├── geo/          # Aeropuertos cercanos, traslados, H3
├── models/       # SQLAlchemy
└── core/         # Settings, db, redis
```
