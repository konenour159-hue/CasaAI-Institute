"""
Sécurité applicative : hachage de mot de passe (bcrypt) et émission/
vérification de tokens JWT (access + refresh).

Conforme au §8 du cahier des charges technique : mots de passe hachés,
tokens d'accès, refresh tokens, expiration des sessions.

Limitation connue (V1) : les refresh tokens sont des JWT stateless (comme
les access tokens), sans table de révocation côté serveur. Un `/logout`
ne peut donc qu'indiquer au client de supprimer ses tokens ; une vraie
révocation nécessiterait une table `refresh_tokens` (ou une blacklist)
— amélioration prévue pour une V2 si le besoin de révocation immédiate
(ex: compte compromis) se confirme.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import bcrypt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings

ALGORITHM = "HS256"


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Levée pour tout token invalide, expiré, ou du mauvais type."""


# --- Mots de passe -----------------------------------------------------------

def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # hash malformé (ne devrait pas arriver en usage normal) -> jamais valide
        return False


# --- JWT -----------------------------------------------------------------

def _create_token(subject: str, role: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,           # user_id (str(UUID))
        "role": role,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),  # identifiant unique du token (utile pour une future révocation)
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(
        subject=str(user_id), role=role, token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(
        subject=str(user_id), role=role, token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Décode et valide un JWT. Lève TokenError si invalide, expiré, ou si le
    type ne correspond pas à celui attendu (empêche d'utiliser un refresh
    token comme access token, ou l'inverse)."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except ExpiredSignatureError as e:
        raise TokenError("Token expiré") from e
    except InvalidTokenError as e:
        raise TokenError("Token invalide") from e

    if payload.get("type") != expected_type.value:
        raise TokenError(f"Type de token invalide : attendu '{expected_type.value}'")

    return payload
