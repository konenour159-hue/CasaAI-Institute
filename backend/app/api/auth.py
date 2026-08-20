"""
Routes d'authentification (§5 cahier fonctionnel, §5 cahier technique).

    POST  /api/auth/register
    POST  /api/auth/login
    POST  /api/auth/refresh
    POST  /api/auth/logout
    GET   /api/auth/me
    PATCH /api/auth/me
    POST  /api/auth/me/password
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenOnly,
    PasswordChangeRequest,
    RefreshRequest,
    TokenPair,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
    UserUpdateRequest,
)
from app.services.auth_service import AuthError, AuthService, EmailAlreadyRegisteredError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> User:
    service = AuthService(db)
    try:
        return service.register(payload)
    except EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=TokenPair)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    service = AuthService(db)
    try:
        user = service.authenticate(payload.email, payload.password)
    except AuthError as e:
        # Message volontairement générique (voir docstring AuthService) :
        # ne révèle jamais si c'est l'email ou le mot de passe qui est en cause,
        # sauf pour le statut de compte, qui n'est pas une information sensible
        # côté énumération (on suppose que l'email a déjà été vérifié).
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return service.issue_tokens(user)


@router.post("/refresh", response_model=AccessTokenOnly)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenOnly:
    service = AuthService(db)
    try:
        access_token = service.refresh_access_token(payload.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return AccessTokenOnly(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)) -> None:
    """Les tokens JWT V1 sont stateless (cf. app/core/security.py) : il n'y a
    rien à invalider côté serveur. Cet endpoint existe pour la forme de l'API
    (§5 cahier technique) et pour un futur passage à une révocation réelle ;
    le client doit dans tous les cas supprimer ses tokens localement."""
    return None


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    service = AuthService(db)
    try:
        return service.update_profile(current_user, payload)
    except EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    service = AuthService(db)
    try:
        service.change_password(current_user, payload)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return None
