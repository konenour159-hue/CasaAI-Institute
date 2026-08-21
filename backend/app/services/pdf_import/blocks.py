"""
Segmentation en blocs de contenu (étapes 8-9 du cahier, §18-21).

Le principe directeur du cahier : « un paragraphe source n'est PAS
automatiquement un bloc ». Plusieurs paragraphes consécutifs relevant du même
contexte sont regroupés, tandis qu'un changement de nature — titre, liste,
code, légende — ouvre une nouvelle unité.

La décision de frontière est isolée dans `should_start_new_block`, appelable
et testable seule, comme le demande le §20.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.pdf_import.classifier import (
    CAPTION,
    CODE,
    FORMULA,
    HEADING,
    LIST_ITEM,
    TABLE_ROW,
    Classification,
)
from app.services.pdf_import.models import Paragraph
from app.services.pdf_import.tables import Table

# Natures de bloc produites.
TEXT_BLOCK = "TEXT"
LIST_BLOCK = "LIST"
CODE_BLOCK = "CODE"
CAPTION_BLOCK = "CAPTION"
TABLE_BLOCK = "TABLE"
FORMULA_BLOCK = "FORMULA"

_BLOCK_KIND_BY_TYPE = {
    LIST_ITEM: LIST_BLOCK,
    CODE: CODE_BLOCK,
    CAPTION: CAPTION_BLOCK,
    TABLE_ROW: TABLE_BLOCK,
    FORMULA: FORMULA_BLOCK,
}


@dataclass
class Block:
    """Unité documentaire : un ou plusieurs paragraphes de même nature.

    Conserve les paragraphes d'origine, et donc la chaîne complète vers les
    lignes et les pages du PDF (§26 traçabilité, §45 compatibilité RAG).
    """

    kind: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    confidence: float = 1.0
    # Renseigné pour les blocs TABLE uniquement : la structure reconstruite
    # par `tables.detect_tables`, en-têtes et cellules.
    table: Table | None = None

    @property
    def text(self) -> str:
        """Texte du bloc. Les paragraphes distincts restent séparés par une
        ligne vide, de sorte que le découpage reste visible en aval."""
        return "\n\n".join(paragraph.text for paragraph in self.paragraphs)

    @property
    def items(self) -> list | dict:
        """Contenu structuré du bloc, tel qu'il sera stocké en JSON.

        Une liste d'items pour une liste (§21 : une liste ne doit pas être
        aplatie en texte), en-têtes et cellules pour un tableau (§22). Vide
        pour les autres natures, dont le texte suffit.
        """
        if self.kind == LIST_BLOCK:
            return [p.text for p in self.paragraphs]
        if self.kind == TABLE_BLOCK and self.table is not None:
            return {"headers": self.table.headers, "rows": self.table.rows}
        return []

    @property
    def page_start(self) -> int:
        return min((p.page_start for p in self.paragraphs), default=-1)

    @property
    def page_end(self) -> int:
        return max((p.page_end for p in self.paragraphs), default=-1)


def should_start_new_block(
    previous: Classification | None,
    current: Classification,
    *,
    previous_table: int | None = None,
    current_table: int | None = None,
) -> bool:
    """Décide si `current` ouvre un nouveau bloc.

    Isolée et sans état pour rester testable indépendamment (§20).

    Un titre n'entre jamais dans un bloc : il ouvre une section, ce dont
    s'occupe `hierarchy`. Sinon, la frontière suit le changement de nature :
    deux paragraphes de texte consécutifs se rejoignent, un passage au code ou
    à une liste ouvre une unité.

    Les index de tableau départagent le cas que la seule nature ne voit pas :
    deux tableaux qui se suivent sont deux blocs, pas un seul de vingt lignes.
    """
    if current.type == HEADING:
        return True
    if previous is None or previous.type == HEADING:
        return True
    if previous_table != current_table:
        return True
    return _BLOCK_KIND_BY_TYPE.get(previous.type, TEXT_BLOCK) != _BLOCK_KIND_BY_TYPE.get(
        current.type, TEXT_BLOCK
    )


@dataclass
class Element:
    """Élément de premier niveau du document : soit un titre, soit un bloc.

    Cette liste à plat, dans l'ordre de lecture, est ce que consomme la
    reconstruction de hiérarchie.
    """

    kind: str  # "HEADING" ou "BLOCK"
    paragraph: Paragraph | None = None
    classification: Classification | None = None
    block: Block | None = None


def _table_index(paragraph: Paragraph) -> int | None:
    return paragraph.lines[0].table if paragraph.lines else None


def segment(
    paragraphs: list[Paragraph],
    classifications: list[Classification],
    tables: list[Table] | None = None,
) -> list[Element]:
    """Paragraphes classés → suite ordonnée de titres et de blocs."""
    by_index = {table.index: table for table in tables or []}
    elements: list[Element] = []
    current_block: Block | None = None
    previous: Classification | None = None
    previous_table: int | None = None

    for paragraph, classification in zip(paragraphs, classifications):
        table_index = _table_index(paragraph)

        if classification.type == HEADING:
            current_block = None
            elements.append(Element(
                kind="HEADING", paragraph=paragraph, classification=classification,
            ))
            previous = classification
            previous_table = table_index
            continue

        if current_block is None or should_start_new_block(
            previous, classification,
            previous_table=previous_table, current_table=table_index,
        ):
            current_block = Block(
                kind=_BLOCK_KIND_BY_TYPE.get(classification.type, TEXT_BLOCK),
                confidence=classification.confidence,
                table=by_index.get(table_index) if table_index is not None else None,
            )
            elements.append(Element(kind="BLOCK", block=current_block))

        current_block.paragraphs.append(paragraph)
        # La confiance d'un bloc est celle de son élément le moins sûr : un
        # bloc n'est pas plus fiable que sa partie la plus douteuse.
        current_block.confidence = min(current_block.confidence, classification.confidence)
        if current_block.table is not None:
            # Un tableau irrégulier reste un tableau, mais le bloc doit porter
            # l'aveu du §22 plutôt que la confiance de la classification.
            current_block.confidence = min(current_block.confidence, current_block.table.confidence)
        previous = classification
        previous_table = table_index

    return elements
