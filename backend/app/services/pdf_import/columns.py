"""
Détection des colonnes et ordre de lecture (§11 — étape 6, phase F).

Le problème est invisible tant qu'on ne regarde que le texte extrait, et
grossier dès qu'on regarde les positions. Sur une page à deux colonnes, les
lignes gauche et droite partagent la même ordonnée : le regroupement par y les
réunit en **une seule ligne**, et le document se lit

    « La donnee est la matiere Le modele apprend ensuite »

au lieu des deux phrases distinctes. Aucune étape ultérieure ne peut rattraper
cela : le mélange est déjà figé dans le texte de la ligne.

La détection repose sur la **gouttière** — une bande verticale que le texte
n'occupe jamais, entre deux colonnes. Elle n'est retenue que si plusieurs
signaux concordent (règle 6 : jamais une décision sur un seul critère), car un
faux positif réordonnerait une page ordinaire, ce qui serait bien pire que le
défaut corrigé. En cas de doute, on retourne toujours « une seule colonne ».

Limite assumée : un tableau à deux colonnes de texte produit lui aussi une
gouttière. Le rapport de qualité signale donc les pages réordonnées, et
l'étape « tableaux » (phase K) reste à venir.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.services.pdf_import.models import Fragment, Page

# Largeur minimale d'une gouttière. Une gouttière typographique réelle mesure
# 12 à 25 pt ; les fausses gouttières viennent de l'estimation approximative de
# la largeur des fragments et restent de l'ordre de quelques points. Le seuil
# suit la taille du corps (un document en 15 pt a des gouttières plus larges)
# avec un plancher absolu.
_MIN_GUTTER_FACTOR = 1.2
_MIN_GUTTER_POINTS = 12.0

# Un fragment qui couvre à lui seul une telle part de la largeur du texte est
# forcément pleine largeur (titre courant sur les deux colonnes, filet, note) :
# il ne peut pas servir à délimiter des colonnes et masquerait la gouttière.
_FULL_WIDTH_RATIO = 0.55

# Une bande n'est une colonne que si elle porte vraiment du texte.
_MIN_BAND_FRAGMENTS = 3
_MIN_BAND_CHARS = 0.15
_MIN_BAND_WIDTH = 0.15

# Ce qui sépare une mise en colonnes d'un tableau à deux colonnes — les deux
# produisent une gouttière, et la géométrie seule ne les distingue pas.
#
# Une colonne de texte est *longue* (une page en compte des dizaines de
# lignes) et *pleine* (le texte va au bout de la mesure à chaque ligne). Une
# cellule de tableau est courte et les cellules d'une même colonne ont des
# longueurs très inégales. Les deux critères doivent être réunis.
#
# En cas d'échec on retombe sur « une seule colonne », c'est-à-dire sur le
# comportement d'avant cette étape : un tableau mal détecté ne perd rien.
_MIN_BAND_ROWS = 6
_MIN_BAND_FILL = 0.45

# Deux colonnes se font face : leurs plages verticales doivent se recouvrir.
# Sans ce contrôle, deux blocs décalés l'un sous l'autre (un encadré suivi
# d'un paragraphe indenté) passeraient pour des colonnes.
_MIN_VERTICAL_OVERLAP = 0.5


@dataclass(frozen=True)
class Column:
    """Une bande verticale de la page portant une colonne de texte."""

    index: int
    x_start: float
    x_end: float

    @property
    def width(self) -> float:
        return self.x_end - self.x_start


@dataclass
class ColumnLayout:
    """Mise en colonnes d'une page, avec la justification de la décision.

    `reasons` est renseigné dans les deux cas — colonnes détectées ou non :
    c'est ce qui permet de comprendre après coup pourquoi une page a été (ou
    n'a pas été) réordonnée, sans relire le PDF.
    """

    columns: list[Column]
    gutters: list[tuple[float, float]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.columns)

    @property
    def is_multi_column(self) -> bool:
        return len(self.columns) > 1

    def column_of(self, fragment: Fragment) -> int:
        """Index de colonne d'un fragment, ou -1 s'il est pleine largeur.

        Un fragment qui enjambe une gouttière n'appartient à aucune colonne :
        c'est un titre ou une légende qui court sur toute la largeur, et il
        doit rester à sa place dans l'ordre de lecture.
        """
        if not self.is_multi_column:
            return 0
        start = fragment.x
        end = fragment.x + fragment.approx_width
        for gutter_start, gutter_end in self.gutters:
            if start < gutter_start and end > gutter_end:
                return -1
        return sum(1 for _, gutter_end in self.gutters if start >= gutter_end)


@dataclass
class ReadingGroup:
    """Un groupe de fragments consécutifs dans l'ordre de lecture.

    `column` vaut -1 pour un groupe pleine largeur. Le découpage en groupes
    est ce qui empêche l'étape suivante de fusionner deux colonnes en une
    seule ligne : elle ne regroupe par ordonnée qu'à l'intérieur d'un groupe.
    """

    column: int
    fragments: list[Fragment]


def _single_column(page: Page, reason: str) -> ColumnLayout:
    return ColumnLayout(
        columns=[Column(index=0, x_start=0.0, x_end=page.width)],
        reasons=[reason],
    )


def _body_font_size(fragments: list[Fragment]) -> float:
    weighted: list[float] = []
    for fragment in fragments:
        weight = max(len(fragment.text.strip()), 1)
        weighted.extend([fragment.font_size] * weight)
    return statistics.median(weighted) if weighted else 0.0


def _empty_runs(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Bandes vides entre les projections horizontales des fragments.

    Travailler sur des intervalles fusionnés plutôt que sur un histogramme
    évite d'avoir à choisir une résolution de bin : les frontières obtenues
    sont exactes.
    """
    merged: list[list[float]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(left[1], right[0]) for left, right in zip(merged, merged[1:])]


def detect_columns(page: Page) -> ColumnLayout:
    """Mise en colonnes d'une page. Renvoie une seule colonne en cas de doute."""
    fragments = [f for f in page.fragments if f.text.strip()]
    if len(fragments) < 2 * _MIN_BAND_FRAGMENTS:
        return _single_column(page, "trop peu de fragments pour conclure")

    area_start = min(f.x for f in fragments)
    area_end = max(f.x + f.approx_width for f in fragments)
    area_width = area_end - area_start
    if area_width <= 0:
        return _single_column(page, "largeur de texte nulle")

    # Les fragments pleine largeur sont retirés du profil : un seul titre
    # courant au-dessus des deux colonnes suffirait sinon à boucher la
    # gouttière et à faire échouer la détection.
    narrow = [f for f in fragments if f.approx_width < area_width * _FULL_WIDTH_RATIO]
    if len(narrow) < 2 * _MIN_BAND_FRAGMENTS:
        return _single_column(page, "fragments majoritairement pleine largeur")

    body = _body_font_size(narrow) or 10.0
    minimum = max(body * _MIN_GUTTER_FACTOR, _MIN_GUTTER_POINTS)

    spans = [(f.x, f.x + f.approx_width) for f in narrow]
    gutters = [(a, b) for a, b in _empty_runs(spans) if b - a >= minimum]
    if not gutters:
        return _single_column(page, f"aucune gouttière d'au moins {minimum:.0f} pt")

    edges = [area_start] + [x for gutter in gutters for x in gutter] + [area_end]
    bands = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]

    total_chars = sum(len(f.text.strip()) for f in narrow)
    grouped: list[list[Fragment]] = [
        [f for f in narrow if start <= f.x <= end] for start, end in bands
    ]

    for (start, end), members in zip(bands, grouped):
        if len(members) < _MIN_BAND_FRAGMENTS:
            return _single_column(page, "une bande ne porte presque aucun texte")
        if sum(len(f.text.strip()) for f in members) < total_chars * _MIN_BAND_CHARS:
            return _single_column(page, "une bande porte une part négligeable du texte")
        if (end - start) < area_width * _MIN_BAND_WIDTH:
            return _single_column(page, "une bande est trop étroite pour une colonne")
        if len({round(f.y, 1) for f in members}) < _MIN_BAND_ROWS:
            return _single_column(page, "une bande compte trop peu de lignes (tableau ?)")
        widths = [f.approx_width for f in members]
        if statistics.median(widths) < max(widths) * _MIN_BAND_FILL:
            return _single_column(page, "une bande est trop irrégulièrement remplie (tableau ?)")

    extents = [(min(f.y for f in m), max(f.y for f in m)) for m in grouped]
    for (low, high), (next_low, next_high) in zip(extents, extents[1:]):
        shorter = min(high - low, next_high - next_low)
        if shorter <= 0:
            continue
        overlap = min(high, next_high) - max(low, next_low)
        if overlap < shorter * _MIN_VERTICAL_OVERLAP:
            return _single_column(page, "les bandes ne se font pas face verticalement")

    return ColumnLayout(
        columns=[Column(index=i, x_start=s, x_end=e) for i, (s, e) in enumerate(bands)],
        gutters=gutters,
        reasons=[
            f"{len(bands)} colonnes séparées par "
            + ", ".join(f"une gouttière de {b - a:.0f} pt" for a, b in gutters)
        ],
    )


def sort_reading_order(page: Page, layout: ColumnLayout | None = None) -> list[ReadingGroup]:
    """Fragments d'une page, regroupés dans l'ordre de lecture.

    Sur une page à colonnes, un élément pleine largeur (titre courant sur
    toute la largeur) découpe la page en zones : les colonnes sont lues l'une
    après l'autre à l'intérieur de chaque zone, et l'élément pleine largeur
    reste à sa place entre les deux. Sans ce découpage, un titre situé au
    milieu de la page se retrouverait rejeté avant ou après tout le corps.
    """
    if layout is None:
        layout = detect_columns(page)

    fragments = sorted(page.fragments, key=lambda f: (-f.y, f.x))
    if not fragments:
        return []
    if not layout.is_multi_column:
        return [ReadingGroup(column=0, fragments=fragments)]

    groups: list[ReadingGroup] = []
    zone: list[Fragment] = []

    def flush() -> None:
        if not zone:
            return
        for column in layout.columns:
            members = [f for f in zone if layout.column_of(f) == column.index]
            if members:
                groups.append(ReadingGroup(column=column.index, fragments=members))
        zone.clear()

    for fragment in fragments:
        if layout.column_of(fragment) < 0:
            flush()
            groups.append(ReadingGroup(column=-1, fragments=[fragment]))
        else:
            zone.append(fragment)
    flush()

    return groups
