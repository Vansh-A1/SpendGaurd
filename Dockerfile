# =============================================================================
# Stage 1: Build React Frontend
# =============================================================================
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Production Python Backend + Static UI Server
# =============================================================================
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies (build-essential, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend codebase and static assets
COPY api/ ./api/
COPY data/ ./data/
COPY decision/ ./decision/
COPY evidence/ ./evidence/
COPY intent/ ./intent/
COPY model/ ./model/
COPY payments/ ./payments/
COPY policy/ ./policy/
COPY session/ ./session/
COPY simulator/ ./simulator/
COPY spendguard/ ./spendguard/
COPY tests/ ./tests/
COPY pyproject.toml ./

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Expose Gateway Port
EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Launch FastAPI Gateway with Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
