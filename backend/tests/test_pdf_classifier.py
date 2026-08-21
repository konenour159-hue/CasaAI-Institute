"""
Classification par score, avec confidence et explicabilité — étape 5.

Le moteur actuel décide par conditions booléennes sur le texte seul, ce qui
promeut en titres des formules, des lignes de tableau, des légendes et de la
sortie SQL. Ici chaque décision combine plusieurs signaux pondérés, conserve
ses raisons (§34) et une confidence (§14).

Les pondérations et les seuils testés ici ont été calibrés sur trois ouvrages
réels — en particulier les paliers de taille de police, dont les sous-titres
réels se situent à 1,2x le corps et non 1,3x comme supposé au départ.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import (
    attach_lines,
    body_font_size,
    classify,
    classify_all,
    extract_pages,
    group_paragraphs,
)
from app.services.pdf_import.classifier import (
    CAPTION,
    CODE,
    HEADING,
    LIST_ITEM,
    PARAGRAPH,
    UNKNOWN,
)
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def classified(pdf_bytes: bytes):
    pages = attach_lines(extract_pages(pdf_bytes))
    body = body_font_size(pages)
    paragraphs = group_paragraphs(pages)
    return paragraphs, classify_all(paragraphs, body)


def find(paragraphs, results, needle: str):
    for paragraph, result in zip(paragraphs, results):
        if needle in paragraph.text:
            return paragraph, result
    raise AssertionError(f"introuvable : {needle!r}")


# --- Code (signal le plus fiable) --------------------------------------------

def test_code_reconnu_par_la_chasse_fixe():
    """Validé sur les ouvrages réels : 29 et 76 paragraphes de code détectés
    dans les deux livres techniques, aucun dans l'ouvrage non technique."""
    paragraphs, results = classified(ALL_FIXTURES["code"]())
    _p, result = find(paragraphs, results, "import pandas")
    assert result.type == CODE
    assert result.confidence > 0.8
    assert "chasse fixe" in result.reasons[0]


def test_prose_voisine_du_code_reste_un_paragraphe():
    paragraphs, results = classified(ALL_FIXTURES["code"]())
    _p, result = find(paragraphs, results, "On importe")
    assert result.type == PARAGRAPH


# --- Légendes (§25) ----------------------------------------------------------

def test_legende_de_figure_n_est_pas_un_titre():
    """« Figure 2 — Architecture du pipeline » ne doit pas devenir un titre,
    malgré sa brièveté et l'absence de ponctuation finale."""
    pdf = build_pdf([[
        Line("Figure 2 - Architecture du pipeline", y=700, size=9),
        Line("Le texte courant reprend ensuite sur cette ligne.", y=670, size=11),
    ]])
    paragraphs, results = classified(pdf)
    _p, result = find(paragraphs, results, "Figure 2")
    assert result.type == CAPTION
    assert result.type != HEADING


# --- Listes ------------------------------------------------------------------

def test_puce_reconnue_comme_item_de_liste():
    paragraphs, results = classified(ALL_FIXTURES["lists"]())
    _p, result = find(paragraphs, results, "Python")
    assert result.type == LIST_ITEM


def test_item_numerote_sans_appui_typographique_reste_une_liste():
    """« 1. Collecter les données » a la même forme qu'un titre numéroté. En
    l'absence de taille ou de graisse distinctive, c'est une liste — c'est
    cette ambiguïté qui faisait disparaître le contenu des listes."""
    pdf = build_pdf([[
        Line("Les etapes sont les suivantes :", y=700, size=11),
        Line("1. Collecter les donnees", y=676, size=11),
        Line("2. Entrainer le modele", y=659, size=11),
    ]])
    paragraphs, results = classified(pdf)
    _p, result = find(paragraphs, results, "Collecter")
    assert result.type == LIST_ITEM


def test_titre_numerote_avec_appui_typographique_reste_un_titre():
    """Contre-épreuve : la même forme numérotée, mais en gros et en gras, est
    bien un titre."""
    pdf = build_pdf([[
        Line("1. Introduction generale", y=700, size=18, font="bold"),
        Line("Le corps du texte commence ici et se poursuit.", y=670, size=11),
    ]])
    paragraphs, results = classified(pdf)
    _p, result = find(paragraphs, results, "Introduction")
    assert result.type == HEADING
    assert result.confidence >= 0.7


# --- Titres ------------------------------------------------------------------

def test_titre_detecte_par_taille_et_graisse():
    paragraphs, results = classified(ALL_FIXTURES["simple_course"]())
    _p, result = find(paragraphs, results, "Intelligence artificielle")
    assert result.type == HEADING
    assert result.confidence >= 0.7
    assert any("police" in reason for reason in result.reasons)


def test_sous_titre_a_1_2x_le_corps_est_retenu():
    """Palier calibré sur les ouvrages réels : leurs sous-titres
    (« Insertion », « Deletion ») sont à 1,2x le corps. Des paliers placés
    trop haut les laissaient tous sous le seuil de décision."""
    pdf = build_pdf([[
        Line("Insertion", y=700, size=12, font="bold"),
        Line("Cette operation ajoute des enregistrements dans la table.", y=676, size=10),
    ]])
    paragraphs, results = classified(pdf)
    _p, result = find(paragraphs, results, "Insertion")
    assert result.type == HEADING
    assert result.confidence >= 0.7


def test_corps_de_texte_n_est_pas_un_titre():
    paragraphs, results = classified(ALL_FIXTURES["simple_course"]())
    _p, result = find(paragraphs, results, "domaine de l'informatique")
    assert result.type == PARAGRAPH


def test_phrase_longue_ne_devient_pas_un_titre():
    """Cas relevé sur un ouvrage réel, où le moteur actuel promeut en titre
    une phrase tronquée du corps de texte."""
    pdf = build_pdf([[
        Line("L'apprentissage est depuis le debut une partie importante de", y=700, size=11),
        Line("l'intelligence artificielle, car il permet de generaliser.", y=683, size=11),
    ]])
    paragraphs, results = classified(pdf)
    assert all(result.type != HEADING for result in results)


def test_document_sans_titre_ne_produit_aucun_titre():
    """Règle 8 : ne pas inventer de structure."""
    _paragraphs, results = classified(ALL_FIXTURES["no_headings"]())
    assert all(result.type != HEADING for result in results)


# --- Confidence et explicabilité (§14, §34) ----------------------------------

def test_chaque_decision_porte_ses_raisons():
    paragraphs, results = classified(ALL_FIXTURES["nested_headings"]())
    for result in results:
        assert result.reasons, "toute décision doit être justifiable"
        assert 0.0 <= result.confidence <= 1.0


def test_element_ambigu_signale_plutot_que_force():
    """§14 : ne pas forcer artificiellement une classification. Un texte sans
    signal typographique fort mais de forme titrée ressort en confidence
    basse, remontée ensuite au rapport de qualité."""
    pdf = build_pdf([[
        Line("Contexte general", y=700, size=11),
        Line("Le texte courant suit immediatement cette ligne isolee.", y=683, size=11),
    ]])
    paragraphs, results = classified(pdf)
    _p, result = find(paragraphs, results, "Contexte general")
    assert result.is_ambiguous or result.type == PARAGRAPH


def test_texte_vide_classe_inconnu():
    from app.services.pdf_import.models import Paragraph

    result = classify(Paragraph(text="   "), body_size=10.0)
    assert result.type == UNKNOWN
    assert result.confidence == 0.0


# --- Intégration avec les étapes précédentes ---------------------------------

def test_titre_sur_plusieurs_lignes_forme_un_seul_titre():
    """Un titre en gros corps réparti sur plusieurs lignes doit être fusionné
    avant classification. Sans mise à l'échelle du seuil d'écart sur la taille
    de police, un titre de 30 pt ressortait en morceaux (« Implementing » /
    « a GPT model from » / « scratch to generate text »)."""
    pdf = build_pdf([[
        Line("Implementing a GPT model", x=72, y=700, size=28, font="bold"),
        Line("from scratch to generate text", x=72, y=664, size=28, font="bold"),
        Line("Le corps du texte reprend ici, dans une taille ordinaire.", x=72, y=600, size=11),
    ]])
    paragraphs, results = classified(pdf)
    title, result = find(paragraphs, results, "Implementing")
    assert "from scratch to generate text" in title.text
    assert result.type == HEADING


def test_hierarchie_de_titres_entierement_reconnue():
    paragraphs, results = classified(ALL_FIXTURES["nested_headings"]())
    headings = [p.text for p, r in zip(paragraphs, results) if r.type == HEADING]
    for expected in ["1. Donnees", "1.1 Donnees structurees", "2. Intelligence artificielle"]:
        assert any(expected in heading for heading in headings), expected


@pytest.mark.parametrize("name", sorted(ALL_FIXTURES))
def test_classification_robuste_sur_toutes_les_fixtures(name):
    paragraphs, results = classified(ALL_FIXTURES[name]())
    assert len(paragraphs) == len(results)
    for result in results:
        assert result.type in (HEADING, PARAGRAPH, CODE, LIST_ITEM, CAPTION, UNKNOWN)
        assert 0.0 <= result.confidence <= 1.0
