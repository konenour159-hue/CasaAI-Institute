from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey, SmallInteger, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.content import CONTENT_STATUS_ENUM
from app.models.enums import ContentStatus


class Resource(Base, TimestampMixin):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String)
    url: Mapped[Optional[str]] = mapped_column(String)
    publisher: Mapped[Optional[str]] = mapped_column(String)
    year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    level: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ContentStatus] = mapped_column(
        CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.PUBLISHED
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


resource_tags = Table(
    "resource_tags",
    Base.metadata,
    Column("resource_id", String, ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    Column("tag", String, primary_key=True),
)

resource_courses = Table(
    "resource_courses",
    Base.metadata,
    Column("resource_id", String, ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    Column("course_id", String, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
)

resource_lessons = Table(
    "resource_lessons",
    Base.metadata,
    Column("resource_id", String, ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    Column("lesson_id", String, ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True),
)

resource_skills = Table(
    "resource_skills",
    Base.metadata,
    Column("resource_id", String, ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class GlossaryTerm(Base, TimestampMixin):
    __tablename__ = "glossary_terms"

    id: Mapped[uuid.UUID] = uuid_pk()
    term: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    term_en: Mapped[Optional[str]] = mapped_column(String)
    definition: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.PUBLISHED
    )


class GovernanceStandard(Base):
    __tablename__ = "governance_standards"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(String)


class GovernanceJurisdiction(Base):
    __tablename__ = "governance_jurisdictions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    focus: Mapped[Optional[str]] = mapped_column(String)
