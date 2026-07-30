# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOBSMITH_PUBLIC_WEB=1 \
    JOBSMITH_PUBLIC_COOKIE_SECURE=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN python -m pip install --no-cache-dir .

COPY --from=frontend-build /build/frontend/dist ./frontend/dist
COPY data/fallback_jobs.json ./data/fallback_jobs.json
COPY data/demo_jobs/ ./data/demo_jobs/

RUN useradd --create-home --uid 10001 jobsmith \
    && chown -R jobsmith:jobsmith /app
USER jobsmith

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port \"${PORT:-10000}\" --proxy-headers --forwarded-allow-ips='*'"]
