"""
Regroupement des fragments en lignes visuelles (étape 2).

Le visiteur pypdf émet un fragment par séquence de dessin de texte, pas par
ligne : une même ligne arrive en plusieurs morceaux dès qu'elle change de
police ou subit un crénage. Mesuré sur les documents de référence : 1,1 à 2,3
fragments par ligne.

Reconstituer la ligne est la toute première brique, et la plus structurante :
c'est elle qui rend enfin mesurables l'écart vertical entre deux lignes (donc
les vraies frontières de paragraphe, aujourd'hui invisibles) et l'alignement
horizontal (donc les colonnes).
"""
from __future__ import annotations

import re
import statistics

from app.services.pdf_import.columns import detect_columns, sort_reading_order
from app.services.pdf_import.models import Fragment, Line, Page

# Deux fragments appartiennent à la même ligne si leur écart vertical reste
# sous cette fraction de la taille de police. Assez large pour absorber les
# exposants et les changements de police, assez étroit pour ne pas fusionner
# deux lignes consécutives (dont l'interligne dépasse la taille de police).
_SAME_LINE_TOLERANCE = 0.45

# En deçà, on considère qu'il n'y a pas d'espace typographique entre deux
# fragments voisins : ils sont recollés sans ajouter d'espace (cas d'un mot
# coupé en deux fragments par un changement de police).
_SPACE_GAP_RATIO = 0.22


def _dominant_font_size(fragments: list[Fragment]) -> float:
    """Taille représentative d'une ligne : la médiane pondérée par la longueur
    du texte. Une ligne de corps comportant un appel de note en petits
    caractères doit rester une ligne de corps."""
    weighted: list[float] = []
    for fragment in fragments:
        weight = max(len(fragment.text.strip()), 1)
        weighted.extend([fragment.font_size] * weight)
    return statistics.median(weighted) if weighted else 0.0


def _join_fragments(fragments: list[Fragment]) -> str:
    """Concatène des fragments déjà triés par x, en insérant une espace
    uniquement là où l'écart horizontal en suggère une."""
    parts: list[str] = []
    previous: Fragment | None = None

    for fragment in fragments:
        text = fragment.text
        if previous is not None:
            gap = fragment.x - (previous.x + previous.approx_width)
            needs_space = gap > previous.font_size * _SPACE_GAP_RATIO
            already_spaced = parts and (parts[-1].endswith(" ") or text.startswith(" "))
            if needs_space and not already_spaced:
                parts.append(" ")
        parts.append(text)
        previous = fragment

    # pypdf insère lui-même des espaces d'ajustement typographique, qui
    # peuvent s'additionner à celles déjà présentes dans le texte source.
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def group_lines(page: Page) -> list[Line]:
    """Fragments d'une page → lignes visuelles, dans l'ordre de lecture.

    Le regroupement par ordonnée n'a lieu qu'à l'intérieur d'une colonne : sur
    une page à deux colonnes, les lignes gauche et droite partagent la même
    ordonnée et seraient sinon réunies en une seule ligne, mêlant deux phrases
    sans rapport (§11). L'ordre des groupes, lui, est celui de la lecture —
    colonne de gauche entière, puis colonne de droite.

    L'ordre horizontal à l'intérieur d'une ligne est rétabli par tri sur x :
    l'ordre d'émission du flux de contenu ne le garantit pas.
    """
    if not page.fragments:
        return []

    layout = detect_columns(page)
    page.column_count = layout.count

    lines: list[Line] = []
    for group in sort_reading_order(page, layout):
        lines.extend(_group_by_row(group.fragments, column=group.column))
    return [line for line in lines if line.text]


def _group_by_row(fragments: list[Fragment], *, column: int) -> list[Line]:
    """Fragments d'une même colonne → lignes, du haut vers le bas."""
    if not fragments:
        return []

    remaining = sorted(fragments, key=lambda f: (-f.y, f.x))
    lines: list[Line] = []
    current: list[Fragment] = [remaining[0]]

    for fragment in remaining[1:]:
        reference = current[0]
        tolerance = max(reference.font_size, fragment.font_size, 1.0) * _SAME_LINE_TOLERANCE
        if abs(fragment.y - reference.y) <= tolerance:
            current.append(fragment)
        else:
            lines.append(_build_line(current, column=column))
            current = [fragment]

    lines.append(_build_line(current, column=column))
    return lines


def _build_line(fragments: list[Fragment], *, column: int = 0) -> Line:
    ordered = sorted(fragments, key=lambda f: f.x)
    return Line(
        text=_join_fragments(ordered),
        page=ordered[0].page,
        x=min(f.x for f in ordered),
        y=statistics.median([f.y for f in ordered]),
        font_size=_dominant_font_size(ordered),
        fragments=ordered,
        column=column,
    )


def attach_lines(pages: list[Page]) -> list[Page]:
    """Remplit `page.lines` pour chaque page, et renvoie la même liste."""
    for page in pages:
        page.lines = group_lines(page)
    return pages


def body_font_size(pages: list[Page]) -> float:
    """Taille de police du corps de texte, définie comme la taille la plus
    fréquente pondérée par la quantité de texte.

    C'est la référence à laquelle comparer une ligne pour juger si elle est
    « plus grosse que le corps » — comparaison qui n'a de sens que
    relativement, les tailles absolues variant d'un document à l'autre (10 pt
    dans un ouvrage, 15 pt dans un autre parmi les documents de référence).
    """
    weighted: list[float] = []
    for page in pages:
        for line in page.lines:
            weight = max(len(line.text), 1)
            weighted.extend([round(line.font_size, 1)] * weight)
    if not weighted:
        return 0.0
    return statistics.mode(weighted)
