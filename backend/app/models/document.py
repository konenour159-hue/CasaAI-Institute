"""
Structure documentaire d'un contenu importé (option B de l'audit PDF).

Ces tables vivent **à côté** de `lesson_sections`, qui reste inchangée :
l'affichage actuel d'une leçon continue de fonctionner à l'identique, et rien
du contenu déjà en base n'est touché. C'est ce qui distingue l'option B d'une
migration du modèle de contenu existant.

Elles portent ce que le modèle plat ne peut pas représenter (§16, §27) :
l'imbrication des sections sur quatre niveaux, la nature de chaque bloc, la
confiance accordée à chaque décision, et surtout la provenance — fichier
d'origine, page de début, page de fin, positions des lignes. Cette traçabilité
est exigée par le §26.

FRONTIÈRE À NE PAS FRANCHIR
---------------------------
Deux corpus distincts cohabitent dans cette base, et ils ne se mélangent pas :

    lesson_sections        le travail pédagogique écrit à la main.
                           Modifiable, illustré, jamais indexé.

    imported_documents     les PDF importés, reconstruits fidèlement.
    document_sections      C'est **le seul** corpus du futur RAG (§45).
    content_blocks         Instantané figé du document : les retouches
                           pédagogiques faites ensuite sur la leçon dérivée
                           ne le modifient pas, pour que les citations
                           renvoient au document et non à sa réécriture.

Le découpage RAG lira `content_blocks`, et rien d'autre. Cette règle est
écrite ici parce qu'elle ne se déduit d'aucun schéma : rien n'empêche
techniquement d'indexer aussi les leçons, c'est un choix de conception.
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


class ImportedDocument(Base):
    """Un PDF importé : l'identité de la source, au-dessus de son arbre.

    Le §45 demande de conserver `source_file` en tête de ce qui rend un
    fragment citable — sans le nom du document, « page 42 » ne veut rien dire.

    `lesson_id` est **facultatif**, et c'est le point important : un document
    peut être importé comme simple référence, pour alimenter le corpus sans
    créer de cours à relire et publier. Un ouvrage de 649 pages a toute sa
    place dans le corpus et aucune comme brouillon de leçon.
    """

    __tablename__ = "imported_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    school_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("schools.id", ondelete="SET NULL")
    )
    # Renseigné quand l'import a aussi produit un cours. La leçon peut être
    # supprimée sans emporter le document : le corpus lui survit.
    lesson_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("lessons.id", ondelete="SET NULL")
    )
    # Rapport de qualité de l'import, conservé pour pouvoir revenir sur ce que
    # le moteur a décidé sans relire le PDF.
    report: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sections: Mapped[list["DocumentSection"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="DocumentSection.position",
    )

    __table_args__ = (
        Index("ix_imported_documents_lesson", "lesson_id"),
        Index("ix_imported_documents_school", "school_id"),
    )


class DocumentSection(Base):
    """Nœud de l'arbre documentaire reconstruit à l'import.

    Rattaché au document et non à la leçon : l'arbre est la représentation du
    PDF, il existe même quand aucun cours n'a été créé. `parent_id` porte
    l'imbrication, absente du modèle plat.
    """

    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("imported_documents.id", ondelete="CASCADE"), nullable=False
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

    document: Mapped["ImportedDocument"] = relationship(back_populates="sections")
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
        Index("ix_document_sections_document", "document_id"),
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
