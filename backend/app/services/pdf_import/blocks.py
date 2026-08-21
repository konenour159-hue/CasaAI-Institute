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
    HEADING,
    LIST_ITEM,
    Classification,
)
from app.services.pdf_import.models import Paragraph

# Natures de bloc produites.
TEXT_BLOCK = "TEXT"
LIST_BLOCK = "LIST"
CODE_BLOCK = "CODE"
CAPTION_BLOCK = "CAPTION"

_BLOCK_KIND_BY_TYPE = {
    LIST_ITEM: LIST_BLOCK,
    CODE: CODE_BLOCK,
    CAPTION: CAPTION_BLOCK,
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

    @property
    def text(self) -> str:
        """Texte du bloc. Les paragraphes distincts restent séparés par une
        ligne vide, de sorte que le découpage reste visible en aval."""
        return "\n\n".join(paragraph.text for paragraph in self.paragraphs)

    @property
    def items(self) -> list[str]:
        """Items d'une liste, un par paragraphe. Vide pour les autres natures
        — le cahier (§21) demande qu'une liste ne soit pas aplatie en texte."""
        return [p.text for p in self.paragraphs] if self.kind == LIST_BLOCK else []

    @property
    def page_start(self) -> int:
        return min((p.page_start for p in self.paragraphs), default=-1)

    @property
    def page_end(self) -> int:
        return max((p.page_end for p in self.paragraphs), default=-1)


def should_start_new_block(previous: Classification | None, current: Classification) -> bool:
    """Décide si `current` ouvre un nouveau bloc.

    Isolée et sans état pour rester testable indépendamment (§20).

    Un titre n'entre jamais dans un bloc : il ouvre une section, ce dont
    s'occupe `hierarchy`. Sinon, la frontière suit le changement de nature :
    deux paragraphes de texte consécutifs se rejoignent, un passage au code ou
    à une liste ouvre une unité.
    """
    if current.type == HEADING:
        return True
    if previous is None or previous.type == HEADING:
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


def segment(paragraphs: list[Paragraph], classifications: list[Classification]) -> list[Element]:
    """Paragraphes classés → suite ordonnée de titres et de blocs."""
    elements: list[Element] = []
    current_block: Block | None = None
    previous: Classification | None = None

    for paragraph, classification in zip(paragraphs, classifications):
        if classification.type == HEADING:
            current_block = None
            elements.append(Element(
                kind="HEADING", paragraph=paragraph, classification=classification,
            ))
            previous = classification
            continue

        if current_block is None or should_start_new_block(previous, classification):
            current_block = Block(
                kind=_BLOCK_KIND_BY_TYPE.get(classification.type, TEXT_BLOCK),
                confidence=classification.confidence,
            )
            elements.append(Element(kind="BLOCK", block=current_block))

        current_block.paragraphs.append(paragraph)
        # La confiance d'un bloc est celle de son élément le moins sûr : un
        # bloc n'est pas plus fiable que sa partie la plus douteuse.
        current_block.confidence = min(current_block.confidence, classification.confidence)
        previous = classification

    return elements
