"""
Logique métier d'authentification.

§5.2 cahier fonctionnel — la connexion doit vérifier, dans l'ordre :
    1. l'existence du compte
    2. les identifiants (mot de passe)
    3. l'état du compte (actif / suspendu / en attente)
    4. le rôle (déterminé côté serveur, jamais fourni par le client)

Toutes les erreurs d'authentification lèvent `AuthError` avec un message
générique côté "existence/identifiants" (ne jamais révéler si c'est l'email
ou le mot de passe qui est incorrect — évite l'énumération de comptes).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.security import (
    TokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import PasswordChangeRequest, TokenPair, UserRegisterRequest, UserUpdateRequest


class AuthError(Exception):
    """Erreur d'authentification générique (compte, identifiants, statut)."""


class EmailAlreadyRegisteredError(Exception):
    """Email déjà utilisé lors d'une inscription."""


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    # --- Inscription -----------------------------------------------------

    def register(self, payload: UserRegisterRequest) -> User:
        if self.users.email_exists(payload.email):
            raise EmailAlreadyRegisteredError(f"L'email {payload.email} est déjà utilisé.")

        user = self.users.create(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=UserRole.LEARNER,  # un visiteur qui s'inscrit devient toujours LEARNER,
                                     # jamais ADMIN (le rôle n'est pas fourni par le client)
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    # --- Connexion -----------------------------------------------------

    def authenticate(self, email: str, password: str) -> User:
        # 1. existence du compte
        user = self.users.get_by_email(email)
        if user is None:
            raise AuthError("Email ou mot de passe incorrect.")

        # 2. identifiants
        if not verify_password(password, user.password_hash):
            raise AuthError("Email ou mot de passe incorrect.")

        # 3. état du compte
        if user.status != AccountStatus.ACTIVE:
            raise AuthError(f"Ce compte n'est pas actif (statut : {user.status.value}).")

        # 4. le rôle est lu depuis `user.role` (base de données), jamais depuis
        # une entrée cliente — c'est déjà garanti structurellement ici.
        self.users.touch_last_login(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id, user.role.value),
        )

    # --- Rafraîchissement --------------------------------------------------

    def refresh_access_token(self, refresh_token: str) -> str:
        try:
            payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        except TokenError as e:
            raise AuthError(str(e)) from e

        user_id = uuid.UUID(payload["sub"])
        user = self.users.get_by_id(user_id)
        if user is None or user.status != AccountStatus.ACTIVE:
            raise AuthError("Compte introuvable ou inactif.")

        return create_access_token(user.id, user.role.value)

    # --- Profil (self-service) ---------------------------------------------

    def update_profile(self, user: User, payload: UserUpdateRequest) -> User:
        """Modifier le nom ne demande rien de plus ; changer l'email exige le
        mot de passe actuel — c'est le seul garde-fou possible ici puisqu'il
        n'y a pas de vérification par email dans ce projet (une session
        détournée ne doit pas pouvoir prendre le contrôle du compte en
        changeant discrètement l'adresse de récupération)."""
        email_changed = payload.email != user.email
        if email_changed:
            if not payload.current_password or not verify_password(payload.current_password, user.password_hash):
                raise AuthError("Mot de passe actuel incorrect.")
            if self.users.email_exists(payload.email):
                raise EmailAlreadyRegisteredError(f"L'email {payload.email} est déjà utilisé.")

        user.first_name = payload.first_name
        user.last_name = payload.last_name
        user.email = payload.email
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: User, payload: PasswordChangeRequest) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise AuthError("Mot de passe actuel incorrect.")
        user.password_hash = hash_password(payload.new_password)
        self.db.commit()
