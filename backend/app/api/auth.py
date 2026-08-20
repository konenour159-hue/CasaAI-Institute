"""
Routes d'authentification (§5 cahier fonctionnel, §5 cahier technique).

    POST  /api/auth/register
    POST  /api/auth/login
    POST  /api/auth/refresh
    POST  /api/auth/logout
    GET   /api/auth/me
    PATCH /api/auth/me
    POST  /api/auth/me/password
    POST  /api/auth/forgot-password
    POST  /api/auth/reset-password

Les routes exposées à un visiteur non authentifié et coûteuses à abuser
(brute-force de mot de passe, création de comptes en masse, spam d'emails de
réinitialisation) sont limitées en débit par IP (cf. app/core/rate_limit.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenOnly,
    ForgotPasswordRequest,
    PasswordChangeRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
    UserUpdateRequest,
)
from app.services.auth_service import AuthError, AuthService, EmailAlreadyRegisteredError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register(request: Request, payload: UserRegisterRequest, db: Session = Depends(get_db)) -> User:
    service = AuthService(db)
    try:
        return service.register(payload)
    except EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
def login(request: Request, payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenPair:
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


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/hour")
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> None:
    # Toujours 204, que l'email existe ou non (cf. AuthService.request_password_reset)
    # — une réponse différente permettrait de deviner quels emails sont inscrits.
    AuthService(db).request_password_reset(payload)
    return None


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    service = AuthService(db)
    try:
        service.reset_password(payload)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return None
