from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import AccountStatus, UserRole


class UserRegisterRequest(BaseModel):
    """§5.1 cahier fonctionnel : nom, prénom, email, mot de passe au minimum."""
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenOnly(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdateRequest(BaseModel):
    """Mise à jour du profil par l'apprenant lui-même (`PATCH /api/auth/me`).

    `current_password` n'est exigé que lorsque l'email change réellement
    (voir AuthService.update_profile) — modifier seulement le nom ne demande
    pas de re-authentification."""
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    current_password: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    """Représentation d'un utilisateur exposée par l'API — jamais le hash
    du mot de passe."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    role: UserRole
    status: AccountStatus
    created_at: datetime
    last_login_at: datetime | None = None
