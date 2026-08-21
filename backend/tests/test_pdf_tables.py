"""
Tableaux (§22) et formules (§23) — phase K.

Les deux partagent la même exigence, posée par la règle 8 : ne rien inventer.
Un tableau reconstruit de travers est pire qu'un paragraphe de texte, parce
qu'il affirme une structure fausse au lieu d'avouer qu'il n'en a pas trouvé.

D'où le poids donné ici aux cas négatifs. Le plus instructif est celui de deux
blocs de texte côte à côte : géométriquement, ils sont indiscernables d'un
tableau — c'est le contenu des cellules qui tranche.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import (
    FORMULA,
    TABLE_ROW,
    analyze_margins,
    attach_lines,
    body_font_size,
    classify_all,
    detect_tables,
    extract_pages,
    group_paragraphs,
    segment,
    split_cells,
)
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def analyzed(pdf_bytes: bytes):
    """Chaîne complète jusqu'aux blocs, tableaux compris."""
    pages = attach_lines(extract_pages(pdf_bytes))
    body = body_font_size(pages)
    analyze_margins(pages, body)
    tables = detect_tables(pages)
    paragraphs = group_paragraphs(pages)
    classifications = classify_all(paragraphs, body)
    return tables, segment(paragraphs, classifications, tables), classifications


def _grid(rows: list[list[str]], *, columns=(72, 260), y: int = 640,
          bold_first: bool = False, leading: int = 20) -> list[Line]:
    lines: list[Line] = []
    for index, row in enumerate(rows):
        font = "bold" if bold_first and index == 0 else "regular"
        for text, x in zip(row, columns):
            lines.append(Line(text, x=x, y=y, size=11, font=font))
        y -= leading
    return lines


# --- Découpage en cellules ---------------------------------------------------

def test_ligne_ordinaire_n_a_qu_une_cellule():
    """Le découpage ne doit se déclencher que sur un écart franc : une ligne
    de prose, même composée de plusieurs fragments, reste d'un seul tenant."""
    pages = attach_lines(extract_pages(ALL_FIXTURES["simple_course"]()))
    for line in pages[0].lines:
        assert len(split_cells(line)) == 1


def test_ligne_de_tableau_est_decoupee():
    pages = attach_lines(extract_pages(ALL_FIXTURES["tables"]()))
    ligne = next(line for line in pages[0].lines if line.text.startswith("KNN"))
    assert [cell.text for cell in split_cells(ligne)] == ["KNN", "Classification"]


# --- Cas positifs ------------------------------------------------------------

def test_tableau_reconstruit_avec_ses_cellules():
    tables, _, _ = analyzed(ALL_FIXTURES["tables"]())
    assert len(tables) == 1
    assert tables[0].headers == ["Algorithme", "Usage"]
    assert tables[0].rows == [["KNN", "Classification"], ["KMeans", "Clustering"]]


def test_tableau_devient_un_bloc_structure():
    """Le §22 demande une structure, pas du texte aplati : les cellules
    doivent survivre jusqu'au bloc, qui est ce qui sera stocké."""
    _, elements, _ = analyzed(ALL_FIXTURES["tables"]())
    block = next(e.block for e in elements if e.block and e.block.kind == "TABLE")
    assert block.items == {
        "headers": ["Algorithme", "Usage"],
        "rows": [["KNN", "Classification"], ["KMeans", "Clustering"]],
    }


def test_lignes_de_tableau_ne_sont_pas_recollees():
    """Sans traitement, les lignes du tableau se fondent dans un même
    paragraphe et le tableau devient indéchiffrable — défaut n° 9 du cahier."""
    _, _, classifications = analyzed(ALL_FIXTURES["tables"]())
    assert sum(1 for c in classifications if c.type == TABLE_ROW) == 3


def test_en_tete_non_identifiable_reste_une_ligne_de_donnees():
    """Rien ne distingue la première ligne : la règle 8 interdit de la
    promouvoir en en-tête, elle part donc dans les données."""
    pdf = build_pdf([_grid([
        ["Paris", "Lyon"], ["Nantes", "Brest"], ["Lille", "Reims"], ["Dijon", "Rouen"],
    ])])
    tables, _, _ = analyzed(pdf)
    assert len(tables) == 1
    assert tables[0].headers is None
    assert len(tables[0].rows) == 4


def test_deux_tableaux_voisins_restent_deux_blocs():
    lines = _grid([["Nom", "Ville"], ["Ada", "Londres"], ["Alan", "Oxford"]], y=640)
    lines += _grid([["Type", "Usage"], ["KNN", "Tri"], ["Arbre", "Choix"]], y=520)
    tables, elements, _ = analyzed(build_pdf([lines]))
    assert len(tables) == 2
    assert sum(1 for e in elements if e.block and e.block.kind == "TABLE") == 2


# --- Cas négatifs : ne pas inventer de structure -----------------------------

@pytest.mark.parametrize("name", [n for n in ALL_FIXTURES if n != "tables"])
def test_aucun_tableau_ailleurs(name):
    tables, _, _ = analyzed(ALL_FIXTURES[name]())
    assert tables == []


def test_deux_colonnes_de_prose_ne_sont_pas_un_tableau():
    """Le cas qui a coûté le plus cher : sur un ouvrage réel, la géométrie
    seule voyait 38 tableaux, presque tous des annotations de figure en deux
    colonnes. Elles s'alignent aussi bien qu'un tableau ; ce qui les trahit,
    c'est que leurs cellules sont des bouts de phrase."""
    pdf = build_pdf([_grid([
        ["A simplified self-attention", "previous and current inputs in a"],
        ["technique to introduce the", "sequence, ensuring temporal order"],
        ["broader idea", "during the text generation"],
    ])])
    tables, _, _ = analyzed(pdf)
    assert tables == []


def test_sortie_de_terminal_alignee_n_est_pas_un_tableau():
    """Relevé sur un ouvrage réel : trois lignes de résultat SQL préfixées
    d'un marqueur s'alignent parfaitement. La chasse fixe tranche."""
    lines = []
    y = 640
    for name, value in [("Alpha", "12"), ("Beta", "34"), ("Gamma", "56")]:
        lines.append(Line(">", x=72, y=y, size=10, font="mono"))
        lines.append(Line(f"{name} {value}", x=200, y=y, size=10, font="mono"))
        y -= 16
    tables, _, _ = analyzed(build_pdf([lines]))
    assert tables == []


def test_deux_lignes_alignees_ne_suffisent_pas():
    """Deux lignes coupées au même endroit restent une coïncidence plausible ;
    un tableau, c'est une régularité établie."""
    pdf = build_pdf([_grid([["Nom", "Ville"], ["Ada", "Londres"]])])
    tables, _, _ = analyzed(pdf)
    assert tables == []


# --- Formules (§23) ----------------------------------------------------------

def test_formule_affichee_detectee():
    _, elements, _ = analyzed(ALL_FIXTURES["formulas"]())
    block = next(e.block for e in elements if e.block and e.block.kind == "FORMULA")
    assert block.text == "E = mc²"


def test_phrase_avec_un_signe_egal_n_est_pas_une_formule():
    """« Le taux d'erreur = 5 % » réunit l'opérateur et la brièveté ; c'est la
    densité de lettres qui l'écarte."""
    _, _, classifications = analyzed(ALL_FIXTURES["formulas"]())
    assert sum(1 for c in classifications if c.type == FORMULA) == 1


def test_formule_n_est_pas_promue_en_titre():
    """Une formule affichée coche presque tous les indices de titre — courte,
    isolée, sans ponctuation finale. Elle doit être tranchée avant."""
    _, _, classifications = analyzed(ALL_FIXTURES["formulas"]())
    formule = [c for c in classifications if c.type == FORMULA]
    assert formule and formule[0].confidence >= 0.6
