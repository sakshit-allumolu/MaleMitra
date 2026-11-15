# Multi-stage Dockerfile for MaleMitra (ಮಳೆ ಮಿತ್ರ)
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/app/data/malemitra.db

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Run unprivileged. /app/data holds uploaded photos, and the SQLite DB when DATABASE_URL is not set (mount a
# volume); backend/app/data receives benchmark output. Both are also made group/world-writable because some
# hosts (Hugging Face Spaces) override the user with their own uid.
RUN useradd --system --uid 10001 --no-create-home malemitra \
    && mkdir -p /app/data \
    && chown -R malemitra /app/data /app/backend/app/data \
    && chmod -R a+rwX /app/data /app/backend/app/data
USER malemitra

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"

# Workers share state through the database (see backend/app/shared.py), so several are safe. uvicorn reads
# WEB_CONCURRENCY. With DATABASE_URL set (PostgreSQL) replicas on different hosts are safe too; do NOT point
# them at one SQLite file over a network filesystem (README, "Known limits").
ENV WEB_CONCURRENCY=2
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
