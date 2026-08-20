# --- Étape 1 : dépendances -------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Versions non épinglées volontairement : ce sont des paquets système
# (compilateur, headers libpq) dont la version suit celle de l'image de
# base python:3.12-slim, pas une dépendance applicative à figer.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# --- Étape 2 : image finale, allégée -----------------------------------------
FROM python:3.12-slim

# libpq5 (runtime uniquement, pas libpq-dev) pour psycopg2-binary
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app . .

RUN chmod +x docker-entrypoint.sh && mkdir -p media && chown app:app media

USER app
ENV PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
