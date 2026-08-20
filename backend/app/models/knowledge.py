from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.content import CONTENT_STATUS_ENUM
from app.models.enums import ContentStatus


class KnowledgeNode(Base, TimestampMixin):
    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String)
    formula: Mapped[Optional[str]] = mapped_column(String)
    guiding_question: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ContentStatus] = mapped_column(
        CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.PUBLISHED
    )

    applications: Mapped[list["KnowledgeNodeApplication"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


knowledge_node_dependencies = Table(
    "knowledge_node_dependencies",
    Base.metadata,
    Column("node_id", String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_node_id", String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
)

# Leçons qui mobilisent ce concept ("usedIn" dans le prototype). Pointe vers
# des leçons, pas vers d'autres nœuds (vérifié empiriquement sur CASA_DATA).
knowledge_node_used_in_lessons = Table(
    "knowledge_node_used_in_lessons",
    Base.metadata,
    Column("node_id", String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("lesson_id", String, ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True),
)


class KnowledgeNodeApplication(Base):
    __tablename__ = "knowledge_node_applications"

    id: Mapped[uuid.UUID] = uuid_pk()
    node_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False)

    node: Mapped["KnowledgeNode"] = relationship(back_populates="applications")


knowledge_node_demos = Table(
    "knowledge_node_demos",
    Base.metadata,
    Column("node_id", String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("demo_id", String, ForeignKey("demos.id", ondelete="CASCADE"), primary_key=True),
)

knowledge_node_labs = Table(
    "knowledge_node_labs",
    Base.metadata,
    Column("node_id", String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("lab_id", String, ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
)
