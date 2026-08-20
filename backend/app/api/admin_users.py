"""
Endpoints admin — gestion des utilisateurs (§22 cahier fonctionnel).
Toutes réservées au rôle SUPER_ADMIN via `require_super_admin` : la
gestion des utilisateurs (recherche, changement de rôle/statut,
suppression) ne fait PAS partie du périmètre ADMIN "contenu" — voir
app/api/deps.py pour le détail des deux niveaux de privilège.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.session import get_db
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.admin import AdminUserListResponse, AdminUserOut, AdminUserUpdateRequest
from app.services.admin_user_service import AdminUserService, SelfModificationError, UserNotFoundError

router = APIRouter(prefix="/api/admin", tags=["admin-users"])


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    role: UserRole | None = Query(default=None),
    status_filter: AccountStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, description="Recherche sur email/nom/prénom"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
) -> AdminUserListResponse:
    items, total = UserRepository(db).list_all(
        role=role, status=status_filter, search=search, limit=limit, offset=offset
    )
    return AdminUserListResponse(
        items=[AdminUserOut.model_validate(u) for u in items], total=total, limit=limit, offset=offset
    )


@router.get("/users/{user_id}", response_model=AdminUserOut)
def get_user(
    user_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)
) -> AdminUserOut:
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    return AdminUserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> AdminUserOut:
    service = AdminUserService(db)
    try:
        updated = service.update_user(actor=admin, target_id=user_id, payload=payload)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SelfModificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AdminUserOut.model_validate(updated)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_super_admin)
) -> None:
    service = AdminUserService(db)
    try:
        service.delete_user(actor=admin, target_id=user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SelfModificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
