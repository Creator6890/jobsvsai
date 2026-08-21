FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY scoring ./scoring
COPY worker ./worker

# The worker runs scoring jobs; like the API it only ever reads its own code.
RUN useradd --system --uid 1001 --create-home appuser && chown -R appuser:appuser /app
USER appuser

# No port to probe, so liveness is "can still reach the queue it consumes".
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5   CMD python -c "import os,redis;redis.from_url(os.environ['REDIS_URL']).ping()" || exit 1

CMD ["python", "-m", "worker.main"]
