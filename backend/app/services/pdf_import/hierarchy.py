"""
Reconstruction de la hiérarchie des titres (étape 7 du cahier, §16-17).

Le cahier exige que cela fonctionne aussi quand les titres ne sont pas
numérotés, quand des niveaux manquent, quand la numérotation est irrégulière
ou quand plusieurs styles coexistent (§17). Le niveau ne peut donc pas être
déduit d'un seul indice.

Deux indices sont combinés, en retenant le plus profond des deux :

- le **rang de taille de police** parmi les titres du document. C'est l'indice
  le plus universel : il ne suppose aucune numérotation, et les mesures sur
  les ouvrages de référence montrent des paliers nets (30 pt de titre de
  chapitre contre 12,5 pt de section ; 14 pt contre 12 pt) ;
- la **profondeur de numérotation** quand elle existe : « 1.1.1 » est un
  niveau 3, quelle que soit sa taille.

Retenir le maximum des deux évite qu'un sous-titre composé dans la même
police que son parent ne remonte au même niveau que lui, tout en gardant un
classement correct sur les documents sans numérotation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.pdf_import.blocks import Block, Element
from app.services.pdf_import.classifier import Classification
from app.services.pdf_import.models import Paragraph

# Profondeur de numérotation : « 1. » → 1, « 1.2 » → 2, « 1.2.3 » → 3.
_DOTTED_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")

# Niveau maximum géré (§16 : au minimum H1 à H4).
MAX_LEVEL = 4


@dataclass
class Section:
    """Nœud de l'arbre documentaire.

    Porte les champs demandés par le §16 : identifiant, titre, niveau, ordre,
    parent, enfants et blocs — plus la provenance, pour rester traçable
    jusqu'aux pages du PDF.
    """

    id: str
    title: str
    level: int
    order: int
    parent_id: str | None = None
    children: list["Section"] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    confidence: float = 1.0
    page_start: int = -1
    page_end: int = -1

    def walk(self):
        """Parcours en profondeur, section courante d'abord."""
        yield self
        for child in self.children:
            yield from child.walk()


def numbering_depth(text: str) -> int:
    """Profondeur de numérotation d'un titre, 0 s'il n'est pas numéroté."""
    match = _DOTTED_RE.match(text.strip())
    if not match:
        return 0
    return len(match.group(1).split("."))


def assign_levels(headings: list[tuple[Paragraph, Classification]]) -> list[int]:
    """Niveau de chaque titre, dans l'ordre d'apparition.

    Les tailles de police sont d'abord classées par ordre décroissant, ce qui
    donne un rang. Un titre numéroté peut ensuite être approfondi si sa
    numérotation l'indique.
    """
    if not headings:
        return []

    sizes = sorted({round(paragraph.font_size, 1) for paragraph, _ in headings}, reverse=True)
    rank_by_size = {size: index + 1 for index, size in enumerate(sizes)}

    levels: list[int] = []
    for paragraph, _classification in headings:
        rank = rank_by_size[round(paragraph.font_size, 1)]
        depth = numbering_depth(paragraph.text)
        levels.append(min(MAX_LEVEL, max(rank, depth) if depth else rank))
    return levels


def build_tree(elements: list[Element]) -> list[Section]:
    """Suite ordonnée de titres et de blocs → arbre de sections.

    Les blocs rencontrés avant tout titre sont rattachés à une section
    d'accueil neutre, plutôt que d'être perdus — même principe que le moteur
    actuel, qui ne doit jamais laisser tomber de contenu.
    """
    headings = [
        (element.paragraph, element.classification)
        for element in elements
        if element.kind == "HEADING" and element.paragraph and element.classification
    ]
    levels = assign_levels(headings)
    level_by_paragraph = {id(paragraph): level for (paragraph, _), level in zip(headings, levels)}

    roots: list[Section] = []
    stack: list[Section] = []
    counter = 0
    orphan: Section | None = None

    def next_id() -> str:
        return f"section_{counter:03d}"

    for element in elements:
        if element.kind == "HEADING" and element.paragraph and element.classification:
            counter += 1
            level = level_by_paragraph[id(element.paragraph)]

            # Un niveau ne peut pas descendre de plus d'un cran d'un coup :
            # sans cela, un document dont le premier titre est un H3
            # produirait un arbre suspendu dans le vide (§17 : niveaux
            # manquants).
            while stack and stack[-1].level >= level:
                stack.pop()
            effective_level = min(level, (stack[-1].level + 1) if stack else 1)

            section = Section(
                id=next_id(),
                title=element.paragraph.text,
                level=effective_level,
                order=len([s for s in (stack[-1].children if stack else roots)]) + 1,
                parent_id=stack[-1].id if stack else None,
                confidence=element.classification.confidence,
                page_start=element.paragraph.page_start,
                page_end=element.paragraph.page_end,
            )

            if stack:
                stack[-1].children.append(section)
            else:
                roots.append(section)
            stack.append(section)
            orphan = None
            continue

        if element.kind == "BLOCK" and element.block:
            if stack:
                target = stack[-1]
            else:
                if orphan is None:
                    counter += 1
                    orphan = Section(
                        id=next_id(), title="Introduction", level=1,
                        order=len(roots) + 1, confidence=0.5,
                    )
                    roots.append(orphan)
                    # Volontairement pas empilé : le premier vrai titre
                    # rencontré doit ouvrir une section sœur, pas un enfant
                    # de cette section d'accueil.
                target = orphan
            target.blocks.append(element.block)
            _extend_pages(target, element.block)

    return roots


def _extend_pages(section: Section, block: Block) -> None:
    if block.page_start < 0:
        return
    section.page_start = block.page_start if section.page_start < 0 else min(section.page_start, block.page_start)
    section.page_end = max(section.page_end, block.page_end)


def flatten(sections: list[Section]) -> list[Section]:
    """Arbre → liste à plat dans l'ordre de lecture."""
    result: list[Section] = []
    for section in sections:
        result.extend(section.walk())
    return result
