"""
Reconstruction de la hiérarchie des titres (étape 7 du cahier, §16-17).

Le cahier exige que cela fonctionne aussi quand les titres ne sont pas
numérotés, quand des niveaux manquent, quand la numérotation est irrégulière
ou quand plusieurs styles coexistent (§17). Le niveau ne peut donc pas être
déduit d'un seul indice.

Deux indices sont combinés, en retenant le plus profond des deux :

- le **palier de taille de police** parmi les titres du document. C'est
  l'indice le plus universel : il ne suppose aucune numérotation, et les
  mesures sur les ouvrages de référence montrent des paliers nets (30 pt de
  titre de chapitre contre 12,5 pt de section ; 14 pt contre 12 pt) ;
- la **profondeur de numérotation** quand elle existe : « 1.1.1 » est un
  niveau 3, quelle que soit sa taille.

Retenir le maximum des deux évite qu'un sous-titre composé dans la même
police que son parent ne remonte au même niveau que lui, tout en gardant un
classement correct sur les documents sans numérotation.

Deux pièges mesurés sur les ouvrages réels, et corrigés ici :

1. **Le surtitre.** « Unit 18 » composé en 12 pt au-dessus de « Using a MySQL
   Database » en 14 pt n'est pas le parent de ce titre : c'est la même tête de
   chapitre, en deux lignes. Traités séparément, le plus petit devenait le
   parent du plus grand et emportait tout le chapitre suivant dans la branche
   précédente. Voir `merge_overline_headings`.

2. **Le rang dense.** Classer les tailles distinctes une à une donnait, sur un
   ouvrage à six tailles de titre, des rangs de 1 à 6 : tout ce qui se situait
   sous la quatrième s'écrasait au niveau 4, tandis que 12 pt et 11,6 pt —
   visuellement le même niveau — se retrouvaient séparés. Les tailles sont
   donc regroupées en paliers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from app.services.pdf_import.blocks import Block, Element
from app.services.pdf_import.classifier import HEADING, Classification
from app.services.pdf_import.models import Paragraph

# Profondeur de numérotation : « 1. » → 1, « 1.2 » → 2, « 1.2.3 » → 3.
_DOTTED_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")

# Niveau maximum géré (§16 : au minimum H1 à H4).
MAX_LEVEL = 4

# Écart relatif en deçà duquel deux tailles de titre relèvent du même palier.
# Calibré sur les trois ouvrages : leurs échelles typographiques progressent
# par bonds de 12 % à 60 % entre niveaux, tandis que des variations de 3 % à
# 7 % cohabitent *à l'intérieur* d'un même niveau (12 et 11,6 pt ; 15 et
# 14 pt ; 12,5 et 12 pt). 8 % sépare les deux sans ambiguïté.
_SIZE_BAND_TOLERANCE = 0.08

# Un surtitre est court par nature — un numéro d'unité, un rappel de partie.
_MAX_OVERLINE_LENGTH = 50

# Et il est collé à son titre : au-delà, ce sont deux titres distincts.
_OVERLINE_GAP_FACTOR = 2.5


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


def size_bands(sizes: list[float]) -> dict[float, int]:
    """Tailles de titre → rang de palier, 1 pour la plus grande.

    Le palier est ouvert par sa plus grande taille, et toutes celles qui
    restent à moins de 8 % d'elle le rejoignent. Comparer à cette taille de
    référence plutôt qu'à la précédente évite qu'une suite de petits écarts
    ne fasse dériver un palier de proche en proche jusqu'à réunir des niveaux
    manifestement distincts.
    """
    bands: dict[float, int] = {}
    rank = 0
    anchor: float | None = None
    for size in sorted(set(sizes), reverse=True):
        if anchor is None or (anchor - size) > anchor * _SIZE_BAND_TOLERANCE:
            rank += 1
            anchor = size
        bands[size] = rank
    return bands


def assign_levels(headings: list[tuple[Paragraph, Classification]]) -> list[int]:
    """Niveau de chaque titre, dans l'ordre d'apparition.

    Les tailles de police sont d'abord regroupées en paliers, ce qui donne un
    rang. Un titre numéroté peut ensuite être approfondi si sa numérotation
    l'indique.
    """
    if not headings:
        return []

    rank_by_size = size_bands([round(paragraph.font_size, 1) for paragraph, _ in headings])

    levels: list[int] = []
    for paragraph, _classification in headings:
        rank = rank_by_size[round(paragraph.font_size, 1)]
        depth = numbering_depth(paragraph.text)
        levels.append(min(MAX_LEVEL, max(rank, depth) if depth else rank))
    return levels


def _is_overline(first: Paragraph, first_result: Classification,
                 second: Paragraph, second_result: Classification) -> bool:
    """Vrai si `first` est le surtitre de `second`.

    Cinq conditions concordantes (règle 6). Aucune ne suffirait : un vrai
    titre parent est lui aussi court et suivi d'un sous-titre — ce qui le
    distingue, c'est que son sous-titre est plus *petit* que lui, et qu'un
    contenu les sépare presque toujours.
    """
    if first_result.type != HEADING or second_result.type != HEADING:
        return False
    if not first.lines or not second.lines:
        return False
    # Un surtitre et son titre ne se répartissent pas sur deux pages.
    if first.page_end != second.page_start:
        return False
    if len(first.text.strip()) > _MAX_OVERLINE_LENGTH:
        return False
    if first.text.strip().endswith((".", "!", "?")):
        return False
    # Le titre doit appartenir à un palier franchement supérieur : à taille
    # égale, ce sont deux titres de même niveau qui se suivent.
    if second.font_size <= first.font_size * (1 + _SIZE_BAND_TOLERANCE):
        return False
    gap = first.lines[-1].y - second.lines[0].y
    return 0 < gap <= second.font_size * _OVERLINE_GAP_FACTOR


def merge_overline_headings(
    paragraphs: list[Paragraph], classifications: list[Classification]
) -> tuple[list[Paragraph], list[Classification]]:
    """Réunit chaque surtitre avec le titre qu'il annonce.

    Relevé sur deux des trois ouvrages de référence : « Unit 18 » au-dessus de
    « Using a MySQL Database », « Chapitre 6 » au-dessus de « Utiliser
    l'apprentissage automatique dans l'IA ». Séparés, le surtitre — plus petit
    donc classé plus profond — devenait le parent de son propre titre, et tout
    le chapitre partait dans la branche précédente.

    Fusionner plutôt que reclasser : ce sont bien deux lignes d'un même titre,
    et les garder distinctes obligerait toute la suite à connaître ce cas.
    """
    merged_paragraphs: list[Paragraph] = []
    merged_results: list[Classification] = []
    index = 0

    while index < len(paragraphs):
        current, result = paragraphs[index], classifications[index]
        following = index + 1
        if following < len(paragraphs) and _is_overline(
            current, result, paragraphs[following], classifications[following]
        ):
            title = paragraphs[following]
            merged_paragraphs.append(Paragraph(
                text=f"{current.text.strip()} {title.text.strip()}",
                lines=current.lines + title.lines,
            ))
            # Le titre porte le niveau ; on garde donc sa décision, en notant
            # la fusion pour que le rapport puisse l'expliquer.
            title_result = classifications[following]
            merged_results.append(replace(
                title_result, reasons=title_result.reasons + ["surtitre réuni au titre"],
            ))
            index += 2
            continue

        merged_paragraphs.append(current)
        merged_results.append(result)
        index += 1

    return merged_paragraphs, merged_results


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
