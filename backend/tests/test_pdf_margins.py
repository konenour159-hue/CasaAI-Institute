"""
En-têtes, pieds de page et numéros de page — étape 4.

Ces tests couvrent le cas que la correction du bug de suppression abusive
avait dû abandonner : un en-tête dont le texte change à chaque page (titre de
chapitre, numéro), impossible à repérer par répétition de texte, mais
parfaitement identifiable par sa bande de position.

Les distances utilisées (33 pt, 35 pt et 5 pt du bord, police plus petite que
le corps) sont celles relevées sur les ouvrages de référence.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import (
    analyze_margins,
    attach_lines,
    body_font_size,
    content_lines,
    extract_pages,
    group_paragraphs,
    looks_like_page_number,
)
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def analyzed(pdf_bytes: bytes):
    pages = attach_lines(extract_pages(pdf_bytes))
    report = analyze_margins(pages, body_font_size(pages))
    return pages, report


def _book_pages(count: int = 6, *, header: str | None = None, footer: str | None = None,
                page_number: bool = True) -> bytes:
    """Un document paginé réaliste : en-tête variable, corps, pied, numéro."""
    pages = []
    for n in range(1, count + 1):
        lines = []
        if header:
            lines.append(Line(header.format(n=n), x=72, y=750, size=8))
        y = 700
        for i in range(6):
            lines.append(Line(f"Ligne {i} de contenu de la page {n} du document.", x=72, y=y, size=11))
            y -= 17
        if footer:
            lines.append(Line(footer, x=72, y=50, size=8))
        if page_number:
            lines.append(Line(str(n), x=300, y=30, size=8))
        pages.append(lines)
    return build_pdf(pages)


# --- Formes de numéro de page (§10) ------------------------------------------

@pytest.mark.parametrize("text", ["12", "4 / 20", "4 sur 20", "Page 4", "p. 7", "- 12 -", "•52"])
def test_formes_de_numero_de_page_reconnues(text):
    assert looks_like_page_number(text) is True


@pytest.mark.parametrize("text", ["1. Introduction", "Chapitre 3", "2024 fut une annee", "Exercice 1"])
def test_un_titre_numerote_n_est_pas_un_numero_de_page(text):
    assert looks_like_page_number(text) is False


# --- Détection par bande de position -----------------------------------------

def test_entete_variable_detecte_par_sa_bande_de_position():
    """Le cas que la détection par texte ne pouvait pas couvrir : l'en-tête
    change à chaque page (« 90 CHAPTER 3 … », « 91 CHAPTER 3 … »), seule sa
    position reste constante."""
    pdf = _book_pages(header="{n} CHAPITRE 3 Mecanismes d'attention", page_number=False)
    pages, report = analyzed(pdf)

    assert report.headers >= 5
    marked = [l.text for p in pages for l in p.lines if l.boilerplate == "HEADER"]
    assert any("CHAPITRE 3" in text for text in marked)

    # Et le contenu, lui, est intégralement conservé.
    kept = " ".join(l.text for l in content_lines(pages))
    assert "Ligne 0 de contenu" in kept
    assert "CHAPITRE 3" not in kept


def test_pied_de_page_et_numero_detectes():
    pdf = _book_pages(footer="report erratum - discuss")
    pages, report = analyzed(pdf)

    kinds = {l.boilerplate for p in pages for l in p.lines if l.boilerplate}
    assert "FOOTER" in kinds
    assert "PAGE_NUMBER" in kinds

    kept = " ".join(l.text for l in content_lines(pages))
    assert "report erratum" not in kept


def test_le_corps_de_page_n_est_jamais_marque():
    """Garde-fou principal : quelle que soit sa récurrence, une ligne du corps
    de page reste du contenu."""
    pdf = _book_pages(header="En-tete du document", footer="Pied du document")
    pages, _ = analyzed(pdf)

    body_marked = [
        l.text for p in pages for l in p.lines
        if l.boilerplate and "contenu" in l.text
    ]
    assert body_marked == []


def test_document_sans_entete_ni_pied_ne_marque_rien():
    """Aucune invention : sur un document qui n'en a pas, rien n'est écarté.
    C'est le cas d'un des ouvrages de référence, dépourvu de titre courant."""
    pdf = _book_pages(header=None, footer=None, page_number=False)
    pages, report = analyzed(pdf)
    assert report.total == 0
    assert all(line.boilerplate is None for page in pages for line in page.lines)


def test_ligne_isolee_non_recurrente_non_marquee():
    """Une seule page ne suffit jamais à établir une bande récurrente."""
    pdf = build_pdf([[
        Line("Titre unique en haut de page", x=72, y=750, size=8),
        Line("Contenu de la page.", x=72, y=700, size=11),
    ]])
    pages, report = analyzed(pdf)
    assert report.total == 0


def test_titre_recurrent_dans_le_corps_reste_du_contenu():
    """Contre-épreuve du bug corrigé à l'étape précédente : « Exercice 1/2/3 »
    au milieu de la page, malgré une numérotation récurrente, n'est pas une
    marge et ne doit jamais être écarté."""
    pages_spec = []
    for n in range(1, 5):
        pages_spec.append([
            Line("Support de cours", x=72, y=750, size=8),
            Line(f"Exercice {n}", x=72, y=650, size=14, font="bold"),
            Line(f"Enonce numero {n} a traiter.", x=72, y=620, size=11),
        ])
    pages, _ = analyzed(build_pdf(pages_spec))
    kept = " ".join(l.text for l in content_lines(pages))
    for n in range(1, 5):
        assert f"Exercice {n}" in kept
    assert "Support de cours" not in kept


# --- Explicabilité (§34) et intégration --------------------------------------

def test_le_rapport_explique_les_bandes_retenues():
    """Chaque décision doit pouvoir être justifiée."""
    pdf = _book_pages(header="En-tete {n}", footer="Pied de page")
    _pages, report = analyzed(pdf)
    assert report.bands
    assert any("HEADER" in band for band in report.bands)
    assert all("pages" in band for band in report.bands)


def test_les_marges_sont_exclues_des_paragraphes():
    """Intégration avec l'étape 3 : une fois annotées, les marges ne
    participent plus à la reconstruction des paragraphes."""
    pdf = _book_pages(header="En-tete {n}", footer="Pied de page")
    pages, _ = analyzed(pdf)
    text = " ".join(p.text for p in group_paragraphs(pages))
    assert "En-tete" not in text
    assert "Pied de page" not in text
    assert "contenu de la page" in text


def test_sans_analyse_prealable_rien_n_est_filtre():
    """`group_paragraphs` reste utilisable seul : sans annotation, aucune
    ligne n'est écartée."""
    pages = attach_lines(extract_pages(_book_pages(header="En-tete {n}")))
    text = " ".join(p.text for p in group_paragraphs(pages))
    assert "En-tete" in text


@pytest.mark.parametrize("name", sorted(ALL_FIXTURES))
def test_analyse_robuste_sur_toutes_les_fixtures(name):
    pages, report = analyzed(ALL_FIXTURES[name]())
    assert report.total >= 0
    for page in pages:
        for line in page.lines:
            assert line.boilerplate in (None, "HEADER", "FOOTER", "PAGE_NUMBER")
