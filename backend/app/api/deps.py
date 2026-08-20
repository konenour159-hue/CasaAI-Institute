"""
Dépendances d'autorisation centralisées (§9 cahier des charges technique) :
« les contrôles seront idéalement centralisés dans des dépendances FastAPI
plutôt que répétés arbitrairement dans chaque route ».

Toute route protégée déclare simplement :
    current_user: User = Depends(get_current_user)
ou, pour restreindre à un rôle :
    admin: User = Depends(require_content_admin)   # ADMIN + SUPER_ADMIN
    admin: User = Depends(require_super_admin)      # SUPER_ADMIN seul
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, TokenType, decode_token
from app.db.session import get_db
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extrait et valide l'access token, charge l'utilisateur correspondant.

    Lève 401 si le token est absent, invalide, expiré, ou si l'utilisateur
    n'existe plus / n'est plus actif. C'est la SEULE porte d'entrée pour
    déterminer l'utilisateur courant : le rôle vient de la base de données
    (rechargé à chaque requête), jamais uniquement du payload du token, pour
    qu'un changement de rôle ou une suspension de compte prenne effet
    immédiatement sans attendre l'expiration du token.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides ou expirés.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except TokenError:
        raise unauthorized

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized

    user = UserRepository(db).get_by_id(user_id)
    if user is None or user.status != AccountStatus.ACTIVE:
        raise unauthorized

    return user


def require_role(*allowed_roles: UserRole):
    """Fabrique une dépendance qui restreint l'accès à une route aux rôles
    donnés. Un apprenant qui appelle une route ADMIN reçoit un 403 — même en
    tapant l'URL directement (§5.4 cahier fonctionnel : la vérification de
    permission côté serveur est non contournable)."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : rôle insuffisant.",
            )
        return current_user

    return dependency


# Raccourcis prêts à l'emploi pour les cas les plus courants.
#
# Deux niveaux de privilège admin (voir models/enums.py pour le détail) :
#   - ADMIN       : gestion de contenu (cours/leçons/import PDF) seulement.
#   - SUPER_ADMIN : sur-ensemble d'ADMIN + utilisateurs, progression
#                   globale, certifications.
#
# `require_admin` est volontairement retiré : son nom prêtait à confusion
# maintenant qu'il existe deux rôles admin. Utiliser explicitement
# `require_content_admin` (cours/leçons/import PDF, les deux rôles) ou
# `require_super_admin` (utilisateurs/progression globale/certifications,
# SUPER_ADMIN seul) selon la route à protéger.
require_super_admin = require_role(UserRole.SUPER_ADMIN)
require_content_admin = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
require_learner_or_admin = require_role(UserRole.LEARNER, UserRole.ADMIN, UserRole.SUPER_ADMIN)
