from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import ContentStatus, LessonDepthKey

CONTENT_STATUS_ENUM = Enum(ContentStatus, name="content_status")


# --- Pathways ----------------------------------------------------------------

class Pathway(Base, TimestampMixin):
    __tablename__ = "pathways"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    profile_label: Mapped[Optional[str]] = mapped_column(String)
    level: Mapped[Optional[str]] = mapped_column(String)
    duration_label: Mapped[Optional[str]] = mapped_column(String)
    color: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Lecture pratique des cours d'un parcours, dans l'ordre défini par
    # pathway_courses.position. viewonly=True : les écritures passent par des
    # insertions explicites sur la table d'association (cf. scripts/seed.py).
    # `secondary` en chaîne : la table pathway_courses n'est définie que plus
    # bas dans ce même module, résolue par SQLAlchemy à la configuration des
    # mappers (après import complet du module), pas à la définition de classe.
    courses: Mapped[list["Course"]] = relationship(
        secondary=lambda: pathway_courses, order_by=lambda: pathway_courses.c.position, viewonly=True,
    )


pathway_prerequisites = Table(
    "pathway_prerequisites",
    Base.metadata,
    Column("pathway_id", String, ForeignKey("pathways.id", ondelete="CASCADE"), primary_key=True),
    Column("prerequisite_pathway_id", String, ForeignKey("pathways.id", ondelete="CASCADE"), primary_key=True),
)

pathway_skills = Table(
    "pathway_skills",
    Base.metadata,
    Column("pathway_id", String, ForeignKey("pathways.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


# --- Courses -------------------------------------------------------------

class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String)
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)
    color: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="course", order_by="Lesson.position", cascade="all, delete-orphan"
    )


course_prerequisites = Table(
    "course_prerequisites",
    Base.metadata,
    Column("course_id", String, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
    Column("prerequisite_course_id", String, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
)

course_skills = Table(
    "course_skills",
    Base.metadata,
    Column("course_id", String, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

pathway_courses = Table(
    "pathway_courses",
    Base.metadata,
    Column("pathway_id", String, ForeignKey("pathways.id", ondelete="CASCADE"), primary_key=True),
    Column("course_id", String, ForeignKey("courses.id", ondelete="RESTRICT"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
)


# --- Demos -----------------------------------------------------------------

class Demo(Base, TimestampMixin):
    __tablename__ = "demos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    component_key: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ContentStatus] = mapped_column(
        CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.PUBLISHED
    )


# --- Lessons -----------------------------------------------------------------

class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("skills.id", ondelete="SET NULL"))
    demo_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("demos.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String)
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[Optional[str]] = mapped_column(String)
    example: Mapped[Optional[str]] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    course: Mapped["Course"] = relationship(back_populates="lessons")
    objectives: Mapped[list["LessonObjective"]] = relationship(
        back_populates="lesson", order_by="LessonObjective.position", cascade="all, delete-orphan"
    )
    sections: Mapped[list["LessonSection"]] = relationship(
        back_populates="lesson", order_by="LessonSection.position", cascade="all, delete-orphan"
    )
    depth_levels: Mapped[list["LessonDepthLevel"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )


class LessonObjective(Base):
    __tablename__ = "lesson_objectives"

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[str] = mapped_column(String, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(String, nullable=False)

    lesson: Mapped["Lesson"] = relationship(back_populates="objectives")


class LessonSection(Base):
    """Structure de la leçon (§12 cahier fonctionnel) : sections ordonnées."""
    __tablename__ = "lesson_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[str] = mapped_column(String, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    # Image illustrant la section (optionnelle). URL absolue ou relative
    # renvoyée par POST /admin/media/images — voir services/storage_service.py.
    image_url: Mapped[Optional[str]] = mapped_column(String)
    image_alt: Mapped[Optional[str]] = mapped_column(String)
    # Petit schéma statique (optionnel), rendu par <MiniDiagram> côté
    # frontend : {type: "hierarchy"|"comparison"|"flow"|"cycle", ...}. Pensé
    # pour aider la compréhension sur les sections qui décrivent une
    # relation/comparaison/processus — pas systématique, voir LessonPage.tsx.
    # none_as_null=True : sans ça, SQLAlchemy stocke un Python None comme le
    # littéral JSON `null` plutôt que SQL NULL sur une colonne JSONB (piège
    # classique) — vérifié empiriquement en écrivant ce champ.
    diagram: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))

    lesson: Mapped["Lesson"] = relationship(back_populates="sections")


class LessonDepthLevel(Base):
    """Lecture à plusieurs niveaux (Essentiel/Technique/Maths/Implémentation/
    Architecture/Gouvernance), fonctionnalité découverte dans le prototype."""
    __tablename__ = "lesson_depth_levels"

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[str] = mapped_column(String, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    depth_key: Mapped[LessonDepthKey] = mapped_column(
        Enum(LessonDepthKey, name="lesson_depth_key"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)

    lesson: Mapped["Lesson"] = relationship(back_populates="depth_levels")

    __table_args__ = (UniqueConstraint("lesson_id", "depth_key", name="uq_lesson_depth"),)
