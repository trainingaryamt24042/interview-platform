# =====================================================================
# Stage 1 — build the React frontend
# =====================================================================
FROM node:20-alpine AS web

WORKDIR /web/frontend

# Build-time env. Empty default → frontend uses RELATIVE /api/v1 calls,
# which work when the API serves the bundle on the same origin.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# =====================================================================
# Stage 2 — Python API + the static frontend assets in one image
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY core/ ./core/
COPY api/  ./api/
# Note: cli/ is for local development only and is NOT copied into the
# production image. Render runs the API server, not the CLI.

# Copy the built frontend so FastAPI can serve it at /
COPY --from=web /web/frontend/dist /app/frontend_dist

# Sensible production defaults. Override via env in render.yaml / fly.toml.
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    SERVE_FRONTEND=1 \
    DATABASE_URL=sqlite:///./data/interview.db

EXPOSE 8000

# Render/Fly inject $PORT at runtime — fall back to 8000 for local docker.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
