"""
Limitation de débit (§ audit — /api/auth/login et /api/auth/register étaient
ouverts sans aucune protection contre le brute-force ou la création de
comptes en masse).

Stockage en mémoire du process : correct pour le déploiement actuel (un seul
worker backend, cf. docker-compose.yml). Si le backend tourne un jour derrière
plusieurs workers/replicas, les limites ne seraient plus partagées entre eux
— passer alors `storage_uri=settings.redis_url` (slowapi sait déjà parler à
Redis, aucun autre changement de code nécessaire).
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
