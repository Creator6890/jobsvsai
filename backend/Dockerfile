FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# curl is used by the container health check; kept to a single small package.
RUN apt-get update && apt-get install -y --no-install-recommends curl     && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/tests ./tests
COPY scoring ./scoring
COPY ingestion ./ingestion
COPY enrichment ./enrichment

# Run unprivileged. The application only reads its code and talks to Postgres and Redis,
# so it never needs to write inside the image.
RUN useradd --system --uid 1001 --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5   CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
