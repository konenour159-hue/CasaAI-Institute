"""
Normalisation, césures et reconstruction des paragraphes — étape 3.

C'est l'étape qui corrige le défaut principal : le moteur actuel sépare les
paragraphes sur les lignes vides, que `extract_text()` ne produit
pratiquement jamais, et agglomère donc tout le texte d'une section en un seul
bloc.

Les seuils testés ici sont calibrés sur des mesures faites sur trois ouvrages
réels : interligne courant de 1,30 à 1,40 fois la taille de police, ruptures
de paragraphe à 2,0 fois et au-delà.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import (
    attach_lines,
    extract_pages,
    group_paragraphs,
    join_lines,
    median_leading,
    normalize_text,
)
from app.services.pdf_import.normalizer import SOFT_HYPHEN, is_hyphenated_break
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def paragraphs_of(fixture_name: str):
    return group_paragraphs(attach_lines(extract_pages(ALL_FIXTURES[fixture_name]())))


# --- Normalisation du texte --------------------------------------------------

def test_espaces_exotiques_ramenes_a_l_espace_ordinaire():
    assert normalize_text("mot suivant") == "mot suivant"
    assert normalize_text("a b") == "a b"


def test_caracteres_invisibles_supprimes():
    assert normalize_text("te​xte﻿") == "texte"


def test_ligatures_decomposees():
    assert normalize_text("ﬁchier") == "fichier"
    assert normalize_text("eﬀort") == "effort"


def test_exposants_preserves():
    """NFKC transformerait « mc² » en « mc2 » et détruirait le sens des
    formules — un des types d'éléments que le cahier demande de préserver."""
    assert normalize_text("E = mc²") == "E = mc²"


def test_typographie_francaise_preservee():
    """Les apostrophes et guillemets typographiques font partie du texte, ils
    ne doivent pas être ramenés à leurs équivalents ASCII."""
    assert normalize_text("l’IA « moderne »") == "l’IA « moderne »"


def test_espaces_multiples_reduits():
    assert normalize_text("trop    d'espaces") == "trop d'espaces"


# --- Césures -----------------------------------------------------------------

def test_mot_coupe_recolle_sans_trait_d_union():
    assert is_hyphenated_break("L'intel-", "ligence artificielle") is True
    assert join_lines(["L'intel-", "ligence artificielle"]) == "L'intelligence artificielle"


def test_trait_d_union_conditionnel_tranche_seul():
    """Le trait d'union conditionnel n'est jamais partie du mot : sa présence
    lève toute ambiguïté."""
    assert is_hyphenated_break(f"cesu{SOFT_HYPHEN}", "re") is True


def test_compose_avec_majuscule_conserve_son_trait_d_union():
    """« franco-/Allemand » est un composé, pas une césure : la majuscule qui
    suit le signale."""
    assert is_hyphenated_break("franco-", "Allemand") is False
    assert join_lines(["franco-", "Allemand"]) == "franco- Allemand"


def test_tiret_isole_n_est_pas_une_cesure():
    """Un tiret précédé de moins de deux caractères de mot (tiret cadratin,
    puce) ne doit pas déclencher de recollage."""
    assert is_hyphenated_break("texte -", "suite") is False


def test_lignes_sans_cesure_jointes_par_une_espace():
    assert join_lines(["Premiere ligne", "seconde ligne"]) == "Premiere ligne seconde ligne"


# --- Interligne et frontières de paragraphe ----------------------------------

def test_interligne_median_mesure():
    """Les fixtures utilisent un pas de `size + 6` : à 11 pt, l'interligne
    attendu est donc de 17 points."""
    pages = attach_lines(extract_pages(ALL_FIXTURES["simple_course"]()))
    assert median_leading(pages) == pytest.approx(17.0, abs=1.0)


def test_ecart_vertical_important_separe_deux_paragraphes():
    """Le cœur de la correction : deux blocs séparés par un blanc vertical
    forment deux paragraphes, alors que le moteur actuel les agglomère."""
    pdf = build_pdf([[
        Line("Premiere phrase du bloc initial.", y=700, size=11),
        Line("Suite immediate du meme bloc.", y=683, size=11),
        # Saut net : plus du double de l'interligne courant.
        Line("Debut d'un second bloc distinct.", y=630, size=11),
        Line("Suite immediate de ce second bloc.", y=613, size=11),
    ]])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))

    assert len(paragraphs) == 2
    assert paragraphs[0].text == "Premiere phrase du bloc initial. Suite immediate du meme bloc."
    assert paragraphs[1].text == "Debut d'un second bloc distinct. Suite immediate de ce second bloc."


def test_interligne_regulier_ne_separe_pas():
    """Contre-épreuve : des lignes régulièrement espacées restent un seul
    paragraphe. Sans cela, on retomberait dans le défaut inverse — un
    paragraphe par ligne."""
    pdf = build_pdf([[
        Line(f"Ligne numero {i} du meme paragraphe.", y=700 - i * 17, size=11)
        for i in range(6)
    ]])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))
    assert len(paragraphs) == 1
    assert len(paragraphs[0].lines) == 6


def test_changement_de_taille_separe():
    """Un titre et le corps qui le suit ne sont jamais le même paragraphe."""
    pdf = build_pdf([[
        Line("Titre de section", y=700, size=18, font="bold"),
        Line("Corps de texte qui suit le titre.", y=670, size=11),
    ]])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))
    assert len(paragraphs) == 2
    assert paragraphs[0].text == "Titre de section"


def test_passage_prose_vers_code_separe():
    """Signal validé sur les ouvrages réels : la chasse fixe distingue le code
    de la prose."""
    paragraphs = paragraphs_of("code")
    texts = [p.text for p in paragraphs]
    assert any("On importe" in t for t in texts)
    code = [p for p in paragraphs if p.mono_ratio > 0.6]
    assert code, "le code doit former ses propres paragraphes"
    assert all("import pandas" in p.text or "read_csv" in p.text for p in code)


def test_sous_titre_en_gras_separe_du_corps_meme_a_taille_proche():
    """Cas relevé sur un ouvrage réel : un sous-titre à 12 pt suivi d'un corps
    à 9,7 pt, soit 19 % d'écart — juste sous le seuil de taille. Sans le
    signal du gras, le titre se retrouvait collé au paragraphe suivant
    (« Deletion Deletion removes from the table… »)."""
    pdf = build_pdf([[
        Line("Deletion", y=700, size=12, font="bold"),
        Line("Deletion removes from the table all matching records.", y=680, size=10),
    ]])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))
    assert len(paragraphs) == 2
    assert paragraphs[0].text == "Deletion"


def test_amorce_en_gras_reste_dans_le_paragraphe():
    """Contre-épreuve : quelques mots en gras en début de ligne ne suffisent
    pas à rompre le paragraphe — seul un gras majoritaire le fait."""
    pdf = build_pdf([[
        Line("Note :", x=72, y=700, size=11, font="bold"),
        Line(" ce point merite une attention particuliere du lecteur.", x=100, y=700, size=11),
        Line("La phrase se poursuit normalement ici.", x=72, y=683, size=11),
    ]])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))
    assert len(paragraphs) == 1
    assert paragraphs[0].bold_ratio < 0.6


def test_retrait_de_premiere_ligne_separe():
    """Certains documents marquent leurs paragraphes par l'indentation plutôt
    que par l'espacement."""
    pdf = build_pdf([[
        Line("Premier paragraphe sans retrait ici.", x=72, y=700, size=11),
        Line("Sa deuxieme ligne revient a la marge.", x=72, y=683, size=11),
        Line("Nouveau paragraphe avec retrait.", x=96, y=666, size=11),
    ]])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))
    assert len(paragraphs) == 2
    assert paragraphs[1].text == "Nouveau paragraphe avec retrait."


def test_paragraphe_continue_d_une_page_a_l_autre():
    """ACQUIS à préserver : un saut de page ne coupe pas un paragraphe. Les
    ordonnées de deux pages différentes ne sont pas comparables, un écart y
    n'y a donc aucun sens."""
    pdf = build_pdf([
        [Line("Une phrase commencee en bas de la premiere page", y=90, size=11)],
        [Line("et achevee en haut de la page suivante.", y=700, size=11)],
    ])
    paragraphs = group_paragraphs(attach_lines(extract_pages(pdf)))
    assert len(paragraphs) == 1
    assert paragraphs[0].text == (
        "Une phrase commencee en bas de la premiere page et achevee en haut de la page suivante."
    )


# --- Traçabilité (§26) -------------------------------------------------------

def test_paragraphe_conserve_ses_pages_d_origine():
    """La provenance doit rester disponible : c'est ce qui manque totalement
    au moteur actuel, et ce dont dépendra le futur découpage RAG."""
    pdf = build_pdf([
        [Line("Debut sur la premiere page", y=90, size=11)],
        [Line("fin sur la seconde.", y=700, size=11)],
    ])
    paragraph = group_paragraphs(attach_lines(extract_pages(pdf)))[0]
    assert paragraph.page_start == 0
    assert paragraph.page_end == 1
    assert len(paragraph.lines) == 2


def test_paragraphe_expose_ses_mesures():
    paragraphs = paragraphs_of("simple_course")
    first = paragraphs[0]
    assert first.font_size > 0
    assert 0.0 <= first.bold_ratio <= 1.0
    assert 0.0 <= first.mono_ratio <= 1.0


# --- Non-régression sur l'ensemble des fixtures ------------------------------

def test_le_defaut_du_bloc_unique_est_corrige():
    """Comparaison directe avec le moteur actuel : là où il produit un unique
    corps de texte, la nouvelle chaîne retrouve les paragraphes distincts."""
    from app.services.pdf_import_service import _chunk_pages_into_sections
    from pypdf import PdfReader
    import io

    data = ALL_FIXTURES["simple_course"]()
    texts = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages]
    ancien = _chunk_pages_into_sections(texts)
    assert len(ancien) == 1
    assert "\n\n" not in ancien[0][1]  # un seul bloc, aucune séparation

    nouveau = group_paragraphs(attach_lines(extract_pages(data)))
    # Titre + trois phrases régulièrement espacées : le titre se détache.
    assert len(nouveau) >= 2
    assert nouveau[0].text == "Intelligence artificielle"


@pytest.mark.parametrize("name", sorted(ALL_FIXTURES))
def test_groupement_robuste_sur_toutes_les_fixtures(name):
    pages = attach_lines(extract_pages(ALL_FIXTURES[name]()))
    for paragraph in group_paragraphs(pages):
        assert paragraph.text.strip()
        assert paragraph.lines
        assert paragraph.page_start >= 0
        assert paragraph.page_end >= paragraph.page_start
