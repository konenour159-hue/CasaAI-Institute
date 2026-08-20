from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Table, Column, func
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import AccountStatus, UserRole


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.LEARNER
    )
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"), nullable=False, default=AccountStatus.ACTIVE
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class LearnerProfileType(Base):
    """Catalogue des personas (Direction, Manager, Consultant, Data Engineer...)."""
    __tablename__ = "learner_profile_types"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)


class Goal(Base):
    """Catalogue des objectifs proposés à l'onboarding."""
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)


# Association simple (pas de colonne supplémentaire) -> Table core suffit.
user_profile_goals = Table(
    "user_profile_goals",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("goal_id", String, ForeignKey("goals.id", ondelete="CASCADE"), primary_key=True),
)

# "Compétences déjà acquises" déclarées à l'onboarding (§7 cahier fonctionnel).
# La FK vers skills.id est déclarée ici mais la table skills vit dans catalog.py ;
# la contrainte est résolue au niveau du MetaData commun, l'ordre d'import n'a
# pas d'importance pour SQLAlchemy (contrairement au script SQL brut).
user_profile_interest_skills = Table(
    "user_profile_interest_skills",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class UserProfile(Base):
    """Informations d'onboarding + préférences (1-1 avec User)."""
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    profile_type_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("learner_profile_types.id", ondelete="SET NULL")
    )
    default_pathway_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("pathways.id", ondelete="SET NULL")
    )
    level: Mapped[Optional[str]] = mapped_column(String)
    career_objectives: Mapped[Optional[str]] = mapped_column(String)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    theme: Mapped[str] = mapped_column(String, nullable=False, default="light")
    reduced_motion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="fr")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="profile")
