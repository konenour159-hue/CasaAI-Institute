"""
Détection des colonnes et ordre de lecture — étape 6 (§11).

Deux exigences opposées, et la seconde compte davantage que la première :

- une page réellement en colonnes doit être lue colonne par colonne ;
- une page ordinaire ne doit **jamais** être réordonnée. Un faux positif
  mélangerait un document parfaitement lisible, alors qu'un faux négatif
  laisse simplement le comportement d'avant cette étape.

D'où le nombre de cas négatifs ci-dessous, et notamment le tableau à deux
colonnes — le cas ambigu par excellence, puisqu'il produit lui aussi une
gouttière.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import (
    attach_lines,
    body_font_size,
    detect_columns,
    extract_pages,
    group_paragraphs,
    sort_reading_order,
)
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf

# Fixtures dont aucune page n'est en colonnes. La liste est explicite plutôt
# que déduite : c'est elle qui garantit qu'un futur ajustement des seuils ne
# se met pas à réordonner des pages ordinaires.
SINGLE_COLUMN_FIXTURES = [
    name for name in ALL_FIXTURES if not name.startswith("two_columns")
]


def pages_of(name: str):
    return attach_lines(extract_pages(ALL_FIXTURES[name]()))


def _two_bands(rows: list[tuple[str, str]], *, left_x: float, right_x: float,
               left_y: float = 700, right_y: float | None = None) -> bytes:
    """Deux blocs de texte côte à côte, à positions maîtrisées."""
    lines: list[Line] = []
    y = left_y
    for left, _ in rows:
        lines.append(Line(left, x=left_x, y=y, size=11))
        y -= 17
    y = left_y if right_y is None else right_y
    for _, right in rows:
        lines.append(Line(right, x=right_x, y=y, size=11))
        y -= 17
    return build_pdf([lines])


ROWS = [
    ("La donnee est la matiere", "Le modele apprend ensuite"),
    ("premiere de tout systeme", "a partir de ces exemples"),
    ("d'apprentissage automatique", "pour generaliser au mieux"),
    ("et de toute analyse serieuse", "les situations rencontrees"),
    ("des phenomenes observes sur", "au cours de son utilisation"),
    ("le terrain par les equipes", "quotidienne par les usagers"),
    ("chargees de la collecte des", "des services concernes par"),
    ("informations elementaires.", "la mise en production.")
]


# --- Cas négatifs : ne rien réordonner sans certitude -----------------------

@pytest.mark.parametrize("name", SINGLE_COLUMN_FIXTURES)
def test_page_ordinaire_jamais_prise_pour_des_colonnes(name):
    for page in pages_of(name):
        layout = detect_columns(page)
        assert layout.count == 1, f"{name} p.{page.number} : {layout.reasons}"


def test_tableau_a_deux_colonnes_n_est_pas_pris_pour_des_colonnes():
    """Un tableau produit une gouttière, comme une mise en colonnes. Ce qui
    l'en distingue : peu de lignes, et des cellules de longueurs très
    inégales. Les lignes du tableau doivent continuer à se lire en travers."""
    page = pages_of("tables")[0]
    assert detect_columns(page).count == 1
    assert any("KNN Classification" in line.text for line in page.lines)


def test_gouttiere_trop_etroite_ignoree():
    """Un simple espacement entre deux blocs n'est pas une gouttière : sans
    largeur minimale, l'estimation approximative de la largeur des fragments
    suffirait à en fabriquer."""
    pdf = _two_bands(ROWS, left_x=72, right_x=210)
    layout = detect_columns(extract_pages(pdf)[0])
    assert layout.count == 1
    assert "gouttière" in layout.reasons[0]


def test_blocs_qui_ne_se_font_pas_face_ne_sont_pas_des_colonnes():
    """Deux blocs décalés verticalement se suivent dans la lecture, ils ne
    sont pas côte à côte — les réordonner n'aurait aucun sens."""
    pdf = _two_bands(ROWS, left_x=72, right_x=330, left_y=700, right_y=400)
    layout = detect_columns(extract_pages(pdf)[0])
    assert layout.count == 1
    assert "face" in layout.reasons[0]


def test_decision_toujours_justifiee():
    """Colonnes ou non, la raison est consignée : c'est ce qui rend la
    décision vérifiable après coup sans relire le PDF."""
    for name in ("simple_course", "tables", "two_columns"):
        for page in pages_of(name):
            assert detect_columns(page).reasons


# --- Cas positifs : lire colonne par colonne --------------------------------

def test_deux_colonnes_detectees():
    layout = detect_columns(pages_of("two_columns")[0])
    assert layout.count == 2
    assert len(layout.gutters) == 1
    start, end = layout.gutters[0]
    assert end - start > 12


def test_colonnes_jamais_fusionnees_en_une_seule_ligne():
    """Le défaut d'origine : à ordonnée égale, gauche et droite formaient une
    seule ligne, et deux phrases sans rapport se retrouvaient collées."""
    for line in pages_of("two_columns")[0].lines:
        assert not ("La donnee est la matiere" in line.text and "Le modele" in line.text)


def test_colonne_de_gauche_lue_entierement_avant_la_droite():
    texts = [line.text for line in pages_of("two_columns")[0].lines]
    derniere_gauche = texts.index("l'algorithme retenu ensuite.")
    premiere_droite = texts.index("Le modele apprend ensuite")
    assert derniere_gauche < premiere_droite


def test_titre_pleine_largeur_reste_en_tete():
    """Un titre qui court sur les deux colonnes traverse la gouttière : il
    n'appartient à aucune colonne et doit garder sa place, sans empêcher la
    détection."""
    page = pages_of("two_columns_with_banner")[0]
    assert page.column_count == 2
    assert page.lines[0].text == "Apprentissage automatique supervise"
    assert page.lines[0].column == -1


def test_derniere_ligne_de_page_garde_sa_position():
    """Le dernier fragment d'une page arrive avec une matrice à zéro : sa
    position n'apparaît dans aucun appel ultérieur du visiteur. Reprise du
    voisin, elle basculait dans l'autre colonne."""
    page = pages_of("two_columns")[0]
    derniere = [line for line in page.lines if line.column == 1][-1]
    assert derniere.text == "principal critere de succes."
    assert derniere.x == pytest.approx(330, abs=1)


def test_groupes_de_lecture_ordonnes_par_colonne():
    page = extract_pages(ALL_FIXTURES["two_columns"]())[0]
    groups = sort_reading_order(page)
    assert [group.column for group in groups] == [0, 1]


# --- Effet sur la suite de la chaîne ----------------------------------------

def test_paragraphes_ne_traversent_pas_la_frontiere_de_colonne():
    """Sans traitement particulier, la dernière ligne d'une colonne absorbe la
    première de la suivante : aucun écart vertical exploitable ne les sépare.
    La ponctuation finale tranche."""
    pages = pages_of("two_columns")
    body_font_size(pages)
    paragraphs = group_paragraphs(pages)
    assert len(paragraphs) == 2
    assert paragraphs[0].text.endswith("l'algorithme retenu ensuite.")
    assert paragraphs[1].text.startswith("Le modele apprend ensuite")
