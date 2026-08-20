from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.content import CONTENT_STATUS_ENUM
from app.models.enums import ContentStatus


class Lab(Base, TimestampMixin):
    __tablename__ = "labs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("schools.id", ondelete="SET NULL"))
    lesson_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("lessons.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String)
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)
    color: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)   # Énoncé (§14)
    environment: Mapped[Optional[str]] = mapped_column(String)
    instructions: Mapped[Optional[str]] = mapped_column(String)
    dataset_ref: Mapped[Optional[str]] = mapped_column(String)
    deliverable: Mapped[Optional[str]] = mapped_column(String)
    evaluation_note: Mapped[Optional[str]] = mapped_column(String)
    # Schéma interactif étape par étape (pipeline de données, requête LLM...),
    # rendu par <InteractiveStepPipeline> côté frontend quand présent — voir
    # LabDetailPage.tsx. Liste de {key, title, summary, detail, highlights}.
    # Nullable : la plupart des labs restent en contenu texte simple.
    interactive_steps: Mapped[Optional[list]] = mapped_column(JSONB)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


lab_skills = Table(
    "lab_skills",
    Base.metadata,
    Column("lab_id", String, ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

lab_modes = Table(
    "lab_modes",
    Base.metadata,
    Column("lab_id", String, ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
    Column("mode", String, primary_key=True),
)
