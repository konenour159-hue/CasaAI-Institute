"""
Extraction enrichie et regroupement en lignes — étape 2 de la restructuration
du moteur d'import PDF.

Ces tests portent sur le nouveau paquet `app.services.pdf_import`, encore
autonome : le service d'import existant n'en dépend pas et sa sortie est
inchangée à ce stade.

Les fixtures sont synthétiques (cf. pdf_fixtures.py). Les seuils et les cas
qu'elles reproduisent viennent en revanche de mesures faites sur trois
ouvrages réels — notamment le piège de la taille de police portée par la
matrice de texte, qui n'apparaît sur aucun PDF fabriqué naïvement.
"""
from __future__ import annotations

import math

import pytest

from app.services.pdf_import import attach_lines, body_font_size, extract_pages
from app.services.pdf_import.extractor import _font_base_name, _style_flags, compose
from tests.pdf_fixtures import ALL_FIXTURES


def pages_of(fixture_name: str):
    return attach_lines(extract_pages(ALL_FIXTURES[fixture_name]()))


# --- Composition des matrices ------------------------------------------------

def test_composition_matrice_identite():
    identity = [1, 0, 0, 1, 0, 0]
    assert compose(identity, identity) == identity


def test_composition_matrice_applique_la_translation_du_ctm():
    """Le décalage porté par la matrice courante doit s'ajouter à celui de la
    matrice de texte — c'est ce qui manquait quand `tm[4]` valait 0 alors que
    le texte commençait en réalité à x=80."""
    tm = [1, 0, 0, 1, 10, 20]
    cm = [1, 0, 0, 1, 70, 700]
    result = compose(tm, cm)
    assert result[4] == 80
    assert result[5] == 720


def test_composition_matrice_combine_les_echelles():
    tm = [2, 0, 0, 2, 0, 0]
    cm = [3, 0, 0, 3, 0, 0]
    result = compose(tm, cm)
    assert math.hypot(result[2], result[3]) == pytest.approx(6.0)


# --- Détection de style depuis le nom de police ------------------------------

@pytest.mark.parametrize(
    "font_name,expected",
    [
        # Noms relevés tels quels sur les trois ouvrages de référence.
        ("DINPro-Bold", (True, False, False)),
        ("Merriweather-Light", (False, False, False)),
        ("Merriweather-LightItalic", (False, True, False)),
        ("FranklinGothic-DemiItal", (True, True, False)),
        ("HumanistMann521-BoldConden", (True, False, False)),
        ("CourierStd", (False, False, True)),
        ("DejaVuSansMono-Bold", (True, False, True)),
        ("NewBaskerville-Roman", (False, False, False)),
    ],
)
def test_style_deduit_du_nom_de_police(font_name, expected):
    assert _style_flags(font_name) == expected


def test_prefixe_de_sous_ensemble_de_police_est_retire():
    """Les polices embarquées portent un préfixe arbitraire (« ABCDEF+ ») qui
    fausserait toute comparaison entre documents."""
    assert _font_base_name({"/BaseFont": "/ABCDEF+Helvetica-Bold"}) == "Helvetica-Bold"
    assert _font_base_name({"/BaseFont": "/Helvetica"}) == "Helvetica"
    assert _font_base_name(None) == ""


# --- Extraction : position, taille, police -----------------------------------

def test_extraction_fournit_position_taille_et_police():
    pages = pages_of("simple_course")
    assert len(pages) == 1
    fragments = pages[0].fragments
    assert fragments

    heading = next(f for f in fragments if "Intelligence artificielle" in f.text)
    assert heading.font_size == pytest.approx(18.0, abs=0.5)
    assert heading.bold is True
    assert heading.x == pytest.approx(72, abs=1)
    assert heading.y == pytest.approx(720, abs=1)


def test_dimensions_de_page_disponibles():
    """Nécessaires pour raisonner en distance aux marges plutôt qu'en
    coordonnées absolues."""
    page = pages_of("simple_course")[0]
    assert page.width == pytest.approx(612)
    assert page.height == pytest.approx(792)
    assert page.distance_from_top(792) == pytest.approx(0)
    assert page.distance_from_bottom(0) == pytest.approx(0)


def test_taille_portee_par_la_matrice_est_correctement_restituee():
    """Cas critique, découvert sur un ouvrage réel : la police est déclarée à
    `Tf 1` et la taille réelle vit dans la matrice de texte. Sans composition,
    tout le document paraît à 1 pt et le signal de taille est perdu."""
    page = pages_of("scaled_text_matrix")[0]

    title = next(f for f in page.fragments if "Titre" in f.text)
    body = next(f for f in page.fragments if "Corps" in f.text)

    assert title.font_size == pytest.approx(20.0, abs=0.5)
    assert body.font_size == pytest.approx(10.0, abs=0.5)
    # Et le rapport titre/corps redevient exploitable comme signal.
    assert title.font_size > body.font_size * 1.5


# --- Regroupement en lignes --------------------------------------------------

def test_fragments_de_meme_ordonnee_forment_une_seule_ligne():
    """Une ligne coupée en trois fragments par un changement de police doit
    être recollée — mesuré entre 1,1 et 2,3 fragments par ligne sur les
    documents réels."""
    page = pages_of("multi_fragment_line")[0]
    assert len(page.fragments) == 4
    assert len(page.lines) == 2

    first = page.lines[0]
    assert first.text == "Le terme important est defini ici."
    assert len(first.fragments) == 3
    assert page.lines[1].text == "Ligne suivante, distincte."


def test_lignes_ordonnees_du_haut_vers_le_bas():
    page = pages_of("nested_headings")[0]
    ys = [line.y for line in page.lines]
    assert ys == sorted(ys, reverse=True)
    assert page.lines[0].text == "1. Donnees"


def test_ratio_de_gras_par_ligne():
    """Un ratio plutôt qu'un booléen : une ligne dont seuls les premiers mots
    sont en gras ne doit pas passer pour un titre."""
    page = pages_of("multi_fragment_line")[0]
    mixed = page.lines[0]
    assert 0 < mixed.bold_ratio < 1

    heading = pages_of("simple_course")[0].lines[0]
    assert heading.bold_ratio == pytest.approx(1.0)


def test_ratio_de_chasse_fixe_identifie_le_code():
    """Signal principal pour séparer du code d'un paragraphe. Validé sur les
    ouvrages réels : 103 et 148 lignes de code détectées dans les deux livres
    techniques, aucune dans l'ouvrage non technique."""
    lines = pages_of("code")[0].lines
    code_lines = [line for line in lines if line.mono_ratio > 0.6]
    texts = [line.text for line in code_lines]
    assert "import pandas as pd" in texts
    assert any("read_csv" in text for text in texts)

    prose = [line for line in lines if line.mono_ratio == 0]
    assert any("On importe" in line.text for line in prose)


def test_taille_du_corps_de_texte_est_la_plus_representee():
    """La taille de référence doit être celle du corps, pas celle du titre —
    les comparaisons de taille n'ont de sens que relativement à elle."""
    pages = pages_of("nested_headings")
    assert body_font_size(pages) == pytest.approx(11.0, abs=0.5)


def test_titres_ressortent_au_dessus_de_la_taille_du_corps():
    """Contrôle de bout en bout du signal de taille sur une hiérarchie."""
    pages = pages_of("nested_headings")
    body = body_font_size(pages)
    bigger = [line.text for page in pages for line in page.lines if line.font_size > body * 1.15]
    assert "1. Donnees" in bigger
    assert "1.1 Donnees structurees" in bigger
    # Une ligne de corps ne doit évidemment pas y figurer.
    assert not any("matiere premiere" in text for text in bigger)


def test_page_sans_texte_ne_produit_aucune_ligne():
    """Cas du PDF scanné (§37) : aucune ligne, mais pas d'erreur."""
    from tests.pdf_fixtures import build_pdf

    pages = attach_lines(extract_pages(build_pdf([[]])))
    assert len(pages) == 1
    assert pages[0].fragments == []
    assert pages[0].lines == []
    assert body_font_size(pages) == 0.0


@pytest.mark.parametrize("name", sorted(ALL_FIXTURES))
def test_extraction_robuste_sur_toutes_les_fixtures(name):
    """Aucune fixture ne doit faire échouer l'extraction, et toute ligne
    produite doit porter des mesures exploitables."""
    pages = attach_lines(extract_pages(ALL_FIXTURES[name]()))
    assert pages
    for page in pages:
        for line in page.lines:
            assert line.text.strip()
            assert line.font_size > 0
            assert 0.0 <= line.bold_ratio <= 1.0
            assert 0.0 <= line.mono_ratio <= 1.0
