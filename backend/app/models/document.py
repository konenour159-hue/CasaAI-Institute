"""
Structure documentaire d'un contenu importé (option B de l'audit PDF).

Ces deux tables vivent **à côté** de `lesson_sections`, qui reste inchangée :
l'affichage actuel d'une leçon continue de fonctionner à l'identique, et rien
du contenu déjà en base n'est touché. C'est ce qui distingue l'option B d'une
migration du modèle de contenu existant.

Elles portent ce que le modèle plat ne peut pas représenter (§16, §27) :
l'imbrication des sections sur quatre niveaux, la nature de chaque bloc, la
confiance accordée à chaque décision, et surtout la provenance — page de
début, page de fin, identifiants des lignes d'origine. Cette traçabilité est
exigée par le §26 et conditionne le futur découpage RAG (§45), qui a besoin de
savoir de quelle page vient chaque fragment.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk


class DocumentSection(Base):
    """Nœud de l'arbre documentaire reconstruit à l'import.

    Rattaché à la leçon créée par l'import : c'est elle qui reste le point
    d'entrée côté application. `parent_id` porte l'imbrication, absente du
    modèle plat.
    """

    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[str] = mapped_column(
        String, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_sections.id", ondelete="CASCADE")
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # Confiance de la décision de classification qui a fait de ce texte un
    # titre. Une valeur basse signale un élément à relire (§14, §28).
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    page_start: Mapped[Optional[int]] = mapped_column(Integer)
    page_end: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    children: Mapped[list["DocumentSection"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan",
        order_by="DocumentSection.position",
    )
    parent: Mapped[Optional["DocumentSection"]] = relationship(
        back_populates="children", remote_side="DocumentSection.id",
    )
    blocks: Mapped[list["ContentBlock"]] = relationship(
        back_populates="section", cascade="all, delete-orphan",
        order_by="ContentBlock.position",
    )

    __table_args__ = (
        # Le cahier demande H1 à H4 (§16) ; au-delà, c'est une erreur de
        # reconstruction, pas une hiérarchie légitime.
        CheckConstraint("level >= 1 AND level <= 4", name="ck_document_section_level"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_document_section_confidence"),
        Index("ix_document_sections_lesson", "lesson_id"),
        Index("ix_document_sections_parent", "parent_id"),
    )


class ContentBlock(Base):
    """Unité de contenu d'une section : texte, liste, code ou légende.

    Distincte d'une « slide » : le cahier (§47) insiste sur le fait qu'un bloc
    est une unité **documentaire**, et que sa transformation en unité
    pédagogique relève d'une étape ultérieure.
    """

    __tablename__ = "content_blocks"

    id: Mapped[uuid.UUID] = uuid_pk()
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # TEXT, LIST, CODE, CAPTION — volontairement une chaîne et non une
    # énumération PostgreSQL : de nouveaux types (TABLE, FORMULA) sont prévus
    # aux étapes suivantes, et faire évoluer un type énuméré natif impose une
    # migration à chaque ajout.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False, default="")
    # Items d'une liste, conservés séparément pour ne pas l'aplatir (§21).
    items: Mapped[Optional[list]] = mapped_column(JSONB(none_as_null=True))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    page_start: Mapped[Optional[int]] = mapped_column(Integer)
    page_end: Mapped[Optional[int]] = mapped_column(Integer)
    # Provenance fine : positions des lignes d'origine dans le PDF. Permet de
    # rouvrir le document au bon endroit et servira d'ancrage au découpage RAG.
    source: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    section: Mapped["DocumentSection"] = relationship(back_populates="blocks")

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_content_block_confidence"),
        Index("ix_content_blocks_section", "section_id"),
    )
