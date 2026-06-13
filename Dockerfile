# Single-image deploy: build the React app, then serve it + the API from one
# FastAPI/uvicorn process. No API key required — the agent runs in its
# deterministic heuristic mode, so the live demo costs nothing in LLM calls.

# ---- stage 1: build the frontend --------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # → /fe/dist

# ---- stage 2: python runtime ------------------------------------------------
FROM python:3.11-slim AS app
WORKDIR /app

# System deps for pdfplumber (lxml/pillow wheels usually cover this; kept lean).
COPY backend/ ./
RUN pip install --no-cache-dir .

COPY sample_data/ /app/sample_data/
COPY --from=frontend /fe/dist /app/static

ENV FRONTEND_DIST=/app/static \
    SEED_ON_STARTUP=true \
    SEED_DATA_DIR=/app/sample_data \
    DATABASE_URL=sqlite:////tmp/finance.db \
    PORT=8000

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
