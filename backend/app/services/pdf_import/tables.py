"""
Reconstruction des tableaux (§22 — phase K).

Un PDF ne contient aucune notion de tableau : seulement du texte posé à des
coordonnées. Ce qui trahit un tableau, c'est la **régularité** — plusieurs
lignes de suite découpées aux mêmes abscisses par des écarts horizontaux bien
plus larges qu'une espace.

Une ligne isolée coupée en deux n'est rien : du texte justifié produit à
l'occasion des espaces énormes. Trois lignes coupées **au même endroit** ne
sont pas un hasard typographique.

Mais la régularité ne suffit pas, et c'est la leçon des mesures : sur un des
ouvrages de référence, la géométrie seule trouvait 38 tableaux, dont presque
aucun n'en était un — des annotations de figure disposées en deux colonnes,
un index, des encadrés. Deux blocs de texte côte à côte s'alignent aussi bien
qu'un tableau. Il a fallu y ajouter le contenu des cellules
(`_cells_look_tabular`), qui ramène le compte à 1.

Le §22 interdit d'inventer les cellules. Quand le doute subsiste, ce module ne
produit donc **aucun** tableau et le texte reste du texte : une structure
fausse serait pire que pas de structure. C'est ce qui écarte aussi les
tableaux aux colonnes irrégulières — reconnaissables comme tableaux à l'œil,
mais impossibles à découper sans deviner.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.services.pdf_import.models import Fragment, Line, Page

# Écart horizontal à partir duquel deux fragments voisins appartiennent à des
# cellules différentes. Une espace typographique vaut environ un quart de
# cadratin ; même très dilatée par la justification elle n'atteint pas ce
# seuil. Exprimé en multiple de la taille de police, avec un plancher.
_CELL_GAP_FACTOR = 1.5
_CELL_GAP_POINTS = 10.0

# Un tableau, c'est une régularité : moins de trois lignes n'en établissent
# aucune, et deux lignes coupées au même endroit restent une coïncidence
# plausible.
_MIN_ROWS = 3

# Tolérance d'alignement des débuts de cellule d'une ligne à l'autre.
_ALIGN_TOLERANCE_FACTOR = 1.0
_ALIGN_TOLERANCE_POINTS = 6.0

# Au-delà, deux lignes découpées ne se suivent plus : ce sont deux passages
# distincts, pas deux lignes d'un même tableau.
_MAX_ROW_SPACING_FACTOR = 3.0

# Ce qui distingue un tableau de deux blocs de texte côte à côte — une légende
# de figure en deux colonnes, un index, un encadré. La géométrie les confond :
# les deux s'alignent parfaitement. Le contenu, lui, les sépare.
#
# Une cellule de tableau est une **valeur close** : « KNN », « 1.75 »,
# « Unit 7. ». Elle commence par une majuscule, un chiffre ou un symbole, et
# tient en quelques mots. Une colonne de prose, elle, se compose de lignes de
# continuation qui commencent en minuscule au milieu d'une phrase.
#
# Mesuré sur les trois ouvrages : les 38 « tableaux » que la seule géométrie
# trouvait dans l'un d'eux étaient presque tous des annotations de figure,
# avec 0,67 à 1,0 de cellules commençant en minuscule ; la vraie table des
# matières d'un autre est à 0,0.
_MAX_LOWERCASE_CELLS = 0.3
_MAX_MEDIAN_CELL_LENGTH = 30

_REGULAR_CONFIDENCE = 0.9


@dataclass(frozen=True)
class Cell:
    x: float
    text: str


@dataclass
class Table:
    """Un tableau reconstruit, avec ses lignes d'origine.

    `headers` vaut None quand rien ne permet de distinguer une ligne d'en-tête
    des autres : le cahier interdit de la supposer (règle 8). Les cellules
    sont alors toutes dans `rows`.
    """

    index: int
    rows: list[list[str]]
    headers: list[str] | None = None
    lines: list[Line] = field(default_factory=list)
    confidence: float = _REGULAR_CONFIDENCE
    reasons: list[str] = field(default_factory=list)

    @property
    def column_count(self) -> int:
        return max((len(row) for row in self.rows), default=0)


def split_cells(line: Line) -> list[Cell]:
    """Découpe une ligne visuelle en cellules, sur les écarts horizontaux.

    Renvoie une seule cellule (donc rien d'exploitable) pour une ligne de
    texte ordinaire. Travaille sur les fragments, seuls porteurs des
    positions : le texte de la ligne, lui, a déjà perdu l'information en
    recollant les fragments avec une simple espace.
    """
    if not line.fragments:
        return []

    threshold = max(line.font_size * _CELL_GAP_FACTOR, _CELL_GAP_POINTS)
    groups: list[list[Fragment]] = [[line.fragments[0]]]

    for previous, fragment in zip(line.fragments, line.fragments[1:]):
        gap = fragment.x - (previous.x + previous.approx_width)
        if gap >= threshold:
            groups.append([fragment])
        else:
            groups[-1].append(fragment)

    cells = [
        Cell(x=group[0].x, text=" ".join(f.text.strip() for f in group).strip())
        for group in groups
    ]
    return [cell for cell in cells if cell.text]


def _aligned(rows: list[list[Cell]], tolerance: float) -> bool:
    """Vrai si toutes les lignes ont le même nombre de cellules, commençant
    aux mêmes abscisses."""
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        return False
    for index in range(widths.pop()):
        positions = [row[index].x for row in rows]
        if max(positions) - min(positions) > tolerance:
            return False
    return True


def _cells_look_tabular(rows: list[list[Cell]]) -> bool:
    """Vrai si le contenu des cellules est celui d'un tableau, pas de la prose.

    Sans ce contrôle, la géométrie seule accepte n'importe quels deux blocs de
    texte côte à côte. En cas d'échec, aucun tableau n'est produit et le texte
    reste du texte : le §22 interdit d'inventer des cellules, et une structure
    fausse serait pire que pas de structure du tout.
    """
    cells = [cell.text for row in rows for cell in row]
    if not cells:
        return False
    lowercase = sum(1 for text in cells if text[:1].islower()) / len(cells)
    if lowercase > _MAX_LOWERCASE_CELLS:
        return False
    return statistics.median(len(text) for text in cells) <= _MAX_MEDIAN_CELL_LENGTH


def _detect_headers(rows: list[list[Cell]], lines: list[Line]) -> bool:
    """Vrai si la première ligne est un en-tête.

    Trois signaux, dont deux doivent concorder (règle 6). Un seul se
    tromperait : la première ligne d'un tableau peut être en gras sans être un
    en-tête, et des libellés courts au-dessus de valeurs longues arrivent
    aussi au milieu d'un tableau.

    Faute de deux signaux, on renonce et tout part dans `rows` : le cahier
    (règle 8) interdit de supposer un en-tête qui n'est pas établi.
    """
    if len(rows) < 2:
        return False

    def has_digits(cells: list[Cell]) -> bool:
        return any(char.isdigit() for cell in cells for char in cell.text)

    def average_length(cells: list[Cell]) -> float:
        return sum(len(cell.text) for cell in cells) / len(cells) if cells else 0.0

    bold = lines[0].bold_ratio > 0.6 and all(line.bold_ratio <= 0.6 for line in lines[1:])
    numeric_contrast = not has_digits(rows[0]) and any(has_digits(row) for row in rows[1:])
    body_lengths = [average_length(row) for row in rows[1:]]
    shorter = average_length(rows[0]) < sum(body_lengths) / len(body_lengths)

    return sum((bold, numeric_contrast, shorter)) >= 2


def _too_far_apart(above: Line, below: Line) -> bool:
    """Vrai si deux lignes découpées sont trop éloignées pour appartenir au
    même tableau."""
    if above.page != below.page:
        return True
    reference = max(above.font_size, below.font_size, 1.0)
    return above.y - below.y > reference * _MAX_ROW_SPACING_FACTOR


def _build(index: int, entries: list[tuple[Line, list[Cell]]]) -> Table | None:
    """Valide un ensemble de lignes découpées, et en fait un tableau — ou non."""
    if len(entries) < _MIN_ROWS:
        return None

    lines = [line for line, _ in entries]
    rows = [cells for _, cells in entries]

    reference = max((line.font_size for line in lines), default=10.0)
    tolerance = max(reference * _ALIGN_TOLERANCE_FACTOR, _ALIGN_TOLERANCE_POINTS)
    if not _aligned(rows, tolerance):
        return None
    if not _cells_look_tabular(rows):
        return None

    has_headers = _detect_headers(rows, lines)
    body = rows[1:] if has_headers else rows
    return Table(
        index=index,
        rows=[[cell.text for cell in row] for row in body],
        headers=[cell.text for cell in rows[0]] if has_headers else None,
        lines=lines,
        confidence=_REGULAR_CONFIDENCE,
        reasons=[f"{len(rows)} lignes découpées aux mêmes abscisses"]
        + (["première ligne reconnue comme en-tête"] if has_headers else []),
    )


def detect_tables(pages: list[Page]) -> list[Table]:
    """Repère les tableaux et annote les lignes concernées.

    Comme pour les marges, les lignes sont **annotées** (`line.table`) plutôt
    que déplacées : la suite de la chaîne garde le texte à sa place et peut
    justifier la décision.
    """
    tables: list[Table] = []

    for page in pages:
        run: list[tuple[Line, list[Cell]]] = []

        def flush(_run=run) -> None:
            table = _build(len(tables), list(_run))
            if table is not None:
                for line in table.lines:
                    line.table = table.index
                tables.append(table)
            _run.clear()

        for line in page.lines:
            # Une ligne à chasse fixe est du code ou une sortie de terminal,
            # pas un tableau — et elle s'aligne à merveille. Relevé sur un
            # ouvrage réel : trois lignes de résultat SQL préfixées d'un
            # marqueur « ➾ » passaient pour un tableau à deux colonnes. La
            # chasse fixe est le signal le plus fiable de toute la chaîne, il
            # doit trancher ici aussi.
            if line.boilerplate or line.mono_ratio > 0.6:
                flush()
                continue
            cells = split_cells(line)
            if len(cells) < 2:
                flush()
                continue
            # Un blanc trop large sépare deux tableaux voisins, il ne les
            # annule pas : on ferme le précédent et on ouvre le suivant.
            if run and _too_far_apart(run[-1][0], line):
                flush()
            run.append((line, cells))
        flush()

    return tables
