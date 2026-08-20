#!/bin/sh
# Applique les migrations Alembic au démarrage du conteneur, puis lance la
# commande passée en CMD (par défaut : uvicorn). Le seed n'est PAS lancé
# automatiquement ici (il doit rester un choix explicite, y compris en
# développement) — voir README pour `docker compose exec backend python -m scripts.seed`.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

echo "[entrypoint] Starting: $@"
exec "$@"
