"""
Gestion des utilisateurs côté admin (§22 cahier fonctionnel).

Garde-fous délibérés : un administrateur ne peut ni changer son propre
rôle, ni suspendre son propre compte, ni se supprimer lui-même — évite
qu'une plateforme se retrouve sans administrateur actif suite à une
manipulation malencontreuse (aucun autre mécanisme de récupération de
compte admin n'existe à ce stade).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.admin import AdminUserUpdateRequest


class SelfModificationError(Exception):
    """Un admin tente une action sur son propre compte qui l'empêcherait
    de continuer à administrer la plateforme."""


class UserNotFoundError(Exception):
    pass


class AdminUserService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def update_user(self, *, actor: User, target_id: uuid.UUID, payload: AdminUserUpdateRequest) -> User:
        target = self.repo.get_by_id(target_id)
        if target is None:
            raise UserNotFoundError(f"Utilisateur {target_id} introuvable.")

        if target.id == actor.id:
            # Cette route est réservée à SUPER_ADMIN (require_super_admin) :
            # `actor` est donc toujours SUPER_ADMIN ici. Se rétrograder
            # soi-même vers ADMIN ou LEARNER retirerait l'accès à cette
            # route même, sans autre mécanisme de récupération — on bloque
            # donc tout changement de son propre rôle qui ne resterait pas
            # SUPER_ADMIN, plutôt que de comparer à UserRole.ADMIN comme
            # avant l'introduction du rôle SUPER_ADMIN.
            if payload.role is not None and payload.role != UserRole.SUPER_ADMIN:
                raise SelfModificationError("Vous ne pouvez pas retirer votre propre rôle super administrateur.")
            if payload.status is not None and payload.status != AccountStatus.ACTIVE:
                raise SelfModificationError("Vous ne pouvez pas suspendre votre propre compte.")

        if payload.role is not None:
            target.role = payload.role
        if payload.status is not None:
            target.status = payload.status

        self.db.commit()
        self.db.refresh(target)
        return target

    def delete_user(self, *, actor: User, target_id: uuid.UUID) -> None:
        if target_id == actor.id:
            raise SelfModificationError("Vous ne pouvez pas supprimer votre propre compte.")

        target = self.repo.get_by_id(target_id)
        if target is None:
            raise UserNotFoundError(f"Utilisateur {target_id} introuvable.")

        self.repo.delete(target)
        self.db.commit()
