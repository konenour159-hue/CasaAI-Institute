from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import AccountStatus, UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        # La colonne email est CITEXT côté PostgreSQL : la comparaison est
        # déjà insensible à la casse au niveau de la base.
        return self.db.query(User).filter(User.email == email).first()

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def create(self, *, first_name: str, last_name: str, email: str, password_hash: str,
               role: UserRole = UserRole.LEARNER) -> User:
        user = User(
            first_name=first_name, last_name=last_name, email=email,
            password_hash=password_hash, role=role,
        )
        self.db.add(user)
        self.db.flush()  # obtient user.id sans committer
        return user

    def touch_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        self.db.flush()

    # --- Administration (§22 cahier fonctionnel) --------------------------

    def list_all(
        self, *, role: UserRole | None = None, status: AccountStatus | None = None,
        search: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role)
        if status:
            stmt = stmt.where(User.status == status)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(User.email.ilike(pattern), User.first_name.ilike(pattern), User.last_name.ilike(pattern))
            )

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            self.db.execute(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.flush()
