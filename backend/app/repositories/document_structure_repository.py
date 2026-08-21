"""
Persistance de la structure documentaire reconstruite à l'import.

Écrit l'arbre produit par `services/pdf_import` dans document_sections et
content_blocks. Ne touche jamais à lesson_sections : les deux représentations
coexistent le temps que le frontend puisse consommer la structure imbriquée.
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.document import ContentBlock, DocumentSection
from app.services.pdf_import.hierarchy import Section


class DocumentStructureRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_for_lesson(self, lesson_id: str, roots: list[Section]) -> int:
        """Remplace intégralement la structure d'une leçon.

        Même convention que le reste de l'administration de contenu (une
        sauvegarde remplace l'existant plutôt que de le fusionner) : cela
        garde l'opération idempotente, un réimport ne laissant pas
        d'anciennes sections orphelines.

        Renvoie le nombre de sections écrites.
        """
        # Les blocs partent en cascade avec leurs sections, de même que les
        # sections enfants — un seul DELETE sur les racines suffit donc.
        self.db.execute(
            delete(DocumentSection).where(DocumentSection.lesson_id == lesson_id)
        )
        self.db.flush()

        written = 0
        for position, root in enumerate(roots):
            written += self._insert(lesson_id, root, parent=None, position=position)
        self.db.flush()
        return written

    def _insert(self, lesson_id: str, section: Section, *, parent: DocumentSection | None,
                position: int) -> int:
        row = DocumentSection(
            lesson_id=lesson_id,
            parent=parent,
            level=section.level,
            position=position,
            title=section.title[:500],
            confidence=section.confidence,
            page_start=section.page_start if section.page_start >= 0 else None,
            page_end=section.page_end if section.page_end >= 0 else None,
        )
        self.db.add(row)

        for block_position, block in enumerate(section.blocks):
            self.db.add(ContentBlock(
                section=row,
                position=block_position,
                kind=block.kind,
                text=block.text,
                items=block.items or None,
                confidence=block.confidence,
                page_start=block.page_start if block.page_start >= 0 else None,
                page_end=block.page_end if block.page_end >= 0 else None,
                source=_source_of(block),
            ))

        written = 1
        for child_position, child in enumerate(section.children):
            written += self._insert(lesson_id, child, parent=row, position=child_position)
        return written

    def get_tree(self, lesson_id: str) -> list[DocumentSection]:
        """Racines de l'arbre d'une leçon, enfants et blocs chargés."""
        return list(
            self.db.execute(
                select(DocumentSection)
                .where(DocumentSection.lesson_id == lesson_id, DocumentSection.parent_id.is_(None))
                .options(selectinload(DocumentSection.blocks))
                .order_by(DocumentSection.position)
            ).scalars()
        )


def _source_of(block) -> dict:
    """Provenance d'un bloc : pages et position des lignes d'origine.

    Volontairement dénormalisée en JSON plutôt qu'en table dédiée — c'est une
    donnée de diagnostic et d'ancrage, jamais un critère de requête.
    """
    lines = [line for paragraph in block.paragraphs for line in paragraph.lines]
    return {
        "paragraph_count": len(block.paragraphs),
        "line_count": len(lines),
        "lines": [
            {"page": line.page, "y": round(line.y, 1), "x": round(line.x, 1)}
            for line in lines[:200]  # borne de sécurité sur un bloc anormalement long
        ],
    }
