"""
Base déclarative SQLAlchemy et mixins communs.

Tous les modèles du package `app.models` héritent de `Base`. Ce fichier ne
doit contenir aucune table métier — uniquement l'infrastructure partagée.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base déclarative pour tous les modèles ORM."""
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    """Colonne standard pour une clé primaire UUID générée côté serveur."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Ajoute created_at / updated_at gérés côté serveur (défaut now())."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
