"""
Filet de sécurité du moteur d'import PDF — étape 1 de la restructuration
(cahier technique §31 : « Avant toute modification importante : lancer les
tests existants, noter leur état »). Il n'en existait aucun.

Ce sont des tests de **caractérisation** : ils décrivent ce que le code fait
*aujourd'hui*, pas ce qu'il devrait faire. Les comportements corrects et les
défauts sont donc verrouillés de la même façon — l'intérêt étant qu'aucune
modification future ne puisse changer l'un ou l'autre sans qu'un test échoue
et rende le changement visible.

Convention de lecture :

    ACQUIS   — comportement correct, ne doit pas régresser.
    DÉFAUT   — comportement fautif constaté. Le test verrouille le bug pour
               qu'on voie précisément quand et comment il est corrigé ; il
               devra être inversé à ce moment-là.

Deux défauts sont des pertes de contenu silencieuses, découvertes en écrivant
ce fichier : voir `test_defaut_grave_*`.
"""
from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

from app.models.catalog import School
from app.services.pdf_import_service import (
    PdfImportService,
    _chunk_pages_into_sections,
    _detect_repeated_boilerplate,
)
from tests.pdf_fixtures import ALL_FIXTURES


def pages_of(fixture_name: str) -> list[str]:
    """Texte brut par page, tel que le service le consomme aujourd'hui."""
    data = ALL_FIXTURES[fixture_name]()
    reader = PdfReader(io.BytesIO(data))
    return [(page.extract_text() or "") for page in reader.pages]


def sections_of(fixture_name: str) -> list[tuple[str, str]]:
    return _chunk_pages_into_sections(pages_of(fixture_name))


# --- Socle : les fixtures sont des PDF valides et lisibles -------------------

@pytest.mark.parametrize("name", sorted(ALL_FIXTURES))
def test_toutes_les_fixtures_sont_des_pdf_lisibles(name):
    """ACQUIS — garde-fou sur le générateur de fixtures lui-même : si une
    fixture cessait de produire un PDF valide, tous les autres tests
    deviendraient trompeurs."""
    data = ALL_FIXTURES[name]()
    assert data.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 1
    assert any((p.extract_text() or "").strip() for p in reader.pages)


# --- Ce qui fonctionne déjà --------------------------------------------------

def test_titre_simple_detecte():
    """ACQUIS — un titre isolé en tête de page est reconnu."""
    sections = sections_of("simple_course")
    assert len(sections) == 1
    assert sections[0][0] == "Intelligence artificielle"


def test_titres_numerotes_detectes():
    """ACQUIS — la numérotation est le signal le plus fiable."""
    titles = [t for t, _ in sections_of("numbered_course")]
    assert titles == ["1. Intelligence artificielle", "2. Machine Learning"]


def test_tous_les_niveaux_de_titre_sont_detectes():
    """ACQUIS — 1., 1.1 et 1.1.1 sont tous reconnus comme des titres."""
    titles = [t for t, _ in sections_of("nested_headings")]
    assert titles == [
        "1. Donnees",
        "1.1 Donnees structurees",
        "1.1.1 Bases relationnelles",
        "1.2 Donnees non structurees",
        "2. Intelligence artificielle",
    ]


def test_document_sans_titre_n_invente_rien():
    """ACQUIS — règle 8 du cahier : ne pas inventer de structure. Le contenu
    est regroupé sous une section d'accueil neutre plutôt que découpé au
    hasard."""
    sections = sections_of("no_headings")
    assert len(sections) == 1
    assert sections[0][0] == "Introduction"
    assert "matiere premiere" in sections[0][1]


def test_entete_pied_et_numero_de_page_sont_filtres():
    """ACQUIS — le filtre d'éléments répétés retire l'en-tête, le pied de page
    et le numéro de page (ce dernier via la normalisation des chiffres)."""
    boilerplate = _detect_repeated_boilerplate(pages_of("headers_footers"))
    assert "cours big data - universite" in boilerplate
    assert "(c) # universite - tous droits reserves" in boilerplate
    assert "#" in boilerplate  # les numéros de page nus


def test_un_paragraphe_continue_d_une_page_a_l_autre():
    """ACQUIS — une fin de page ne coupe pas un paragraphe en cours. C'est une
    correction déjà acquise (l'ancienne version faisait « une page = une
    section ») : elle ne doit pas être perdue dans la restructuration."""
    pages = ["Titre A\nDebut de phrase qui", "se poursuit sur la page suivante."]
    sections = _chunk_pages_into_sections(pages)
    assert len(sections) == 1
    assert sections[0][1] == "Debut de phrase qui se poursuit sur la page suivante."


# --- Défauts graves : perte silencieuse de contenu ---------------------------

def test_defaut_grave_titres_numerotes_recurrents_effacent_tout_le_document():
    """DÉFAUT (grave) — perte totale de contenu.

    `_detect_repeated_boilerplate` normalise les chiffres (`\\d+ → #`) pour
    tolérer un numéro de page variable. Effet de bord : des titres légitimes
    qui ne diffèrent que par leur numéro (« Exercice 1 », « Exercice 2 »…)
    deviennent identiques une fois normalisés, dépassent le seuil de
    répétition, et sont supprimés comme du bruit — avec leur contenu.

    Sur cette fixture, l'import produit **zéro section** : le document entier
    disparaît sans le moindre avertissement. C'est aussi une violation de la
    règle 6 du cahier (« ne jamais supprimer un élément sur la base d'une
    règle unique »).
    """
    sections = sections_of("repeated_numbered_headings")
    assert sections == [], "Comportement fautif attendu ici — à inverser une fois corrigé"


def test_defaut_grave_items_de_liste_numerotee_disparaissent():
    """DÉFAUT (grave) — perte de contenu.

    « 1. Collecter les donnees » satisfait la regex de titre numéroté au même
    titre que « 1. Introduction ». Chaque item devient donc une section sans
    corps, et les sections vides sont écartées en fin de traitement : les
    étapes de la procédure sont purement et simplement absentes du résultat.
    """
    sections = sections_of("lists")
    body = " ".join(b for _, b in sections)
    assert "Collecter les donnees" not in body
    assert "Entrainer le modele" not in body
    assert "Evaluer les resultats" not in body


# --- Défauts connus, sans perte de contenu -----------------------------------

def test_defaut_paragraphes_fusionnes_en_un_seul_bloc():
    """DÉFAUT — c'est le défaut principal, et l'inverse de ce que supposait le
    cahier (« chaque paragraphe devient un bloc »).

    Le découpage de paragraphe repose sur les lignes vides, que
    `extract_text()` ne produit quasiment jamais. Les trois paragraphes
    distincts de la fixture arrivent donc collés en un seul corps de texte.
    """
    sections = sections_of("simple_course")
    body = sections[0][1]
    assert "\n\n" not in body, "aucune séparation de paragraphe n'est produite"
    assert body.count(".") >= 3, "les trois phrases sont bien là, mais fusionnées"


def test_defaut_hierarchie_totalement_plate():
    """DÉFAUT — « 1.1.1 Bases relationnelles » est un frère de « 1. Donnees »,
    pas son descendant. Le niveau de titre n'est ni calculé ni conservé : la
    sortie est une liste ordonnée sans imbrication (cf. modèle de données
    plat, décision d'architecture option B)."""
    sections = sections_of("nested_headings")
    assert all(isinstance(s, tuple) and len(s) == 2 for s in sections)
    # Aucune information de niveau nulle part dans la sortie.
    assert not any("level" in str(s) for s in sections)


def test_defaut_liste_a_puces_aplatie_dans_le_paragraphe():
    """DÉFAUT — les puces sont recollées dans le texte courant au lieu de
    former une structure de liste."""
    body = sections_of("lists")[0][1]
    assert "- Python - Java - C++" in body


def test_defaut_colonnes_entrelacees_non_reordonnees():
    """DÉFAUT — sur un flux entrelacé, les deux colonnes sont lues en
    alternance : le texte final mélange les deux et devient incohérent.
    Aucune détection de colonne n'existe."""
    body = sections_of("two_columns")[0][1]
    assert "La donnee est la matiere Le modele apprend ensuite" in body


def test_defaut_mot_coupe_non_reconstruit():
    """DÉFAUT — la césure de fin de ligne n'est pas traitée : « intel- » et
    « ligence » restent séparés par une espace."""
    body = sections_of("hyphenation")[0][1]
    assert "intel- ligence" in body
    assert "intelligence artificielle" not in body
    # À conserver après correction : un vrai mot composé ne doit pas être recollé.
    assert "porte-parole" in body


def test_defaut_code_traite_comme_du_texte_ordinaire():
    """DÉFAUT — le code est fondu dans le paragraphe, alors que sa police à
    chasse fixe est un signal exploitable (disponible via le visiteur pypdf)."""
    body = sections_of("code")[0][1]
    assert "import pandas as pd" in body
    assert "df = pd.read_csv('data.csv')" in body


def test_defaut_tableau_aplati_sans_structure():
    """DÉFAUT — les cellules sont recollées en une ligne de texte ; ni
    en-têtes ni lignes ne sont reconstitués."""
    sections = sections_of("tables")
    body = " ".join(b for _, b in sections)
    assert "Algorithme Usage" in body or "KNN Classification" in body


def test_defaut_aucune_tracabilite_vers_le_pdf_source():
    """DÉFAUT — la sortie est une paire (titre, corps) : ni page d'origine, ni
    identifiant d'élément, ni position. C'est ce que la restructuration doit
    apporter (§26), et ce dont dépend la future architecture RAG (§45)."""
    sections = sections_of("complex_course")
    assert sections
    for section in sections:
        assert len(section) == 2
        assert all(isinstance(part, str) for part in section)


# --- Chemin complet, avec base de données ------------------------------------

def test_import_complet_cree_un_cours_et_une_lecon(db_session):
    """ACQUIS — contrat de bout en bout du service : un import produit un
    cours et une leçon en DRAFT, avec les sections rattachées et le nombre de
    pages remonté. C'est ce contrat que la restructuration ne doit pas casser
    (§48, critère 18)."""
    db_session.add(School(id="pdf-test-school", name="École", short_name="PDF", color="#000000"))
    db_session.commit()

    course, lesson, page_count, warning = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES["complex_course"](),
        filename="cours_test.pdf",
        school_id="pdf-test-school",
    )

    assert page_count == 2
    assert warning is None
    assert course.status.value == "DRAFT"
    assert lesson.status.value == "DRAFT"
    assert course.title == "Cours Test"  # dérivé du nom de fichier
    assert len(lesson.sections) >= 2
    assert all(s.title and s.body for s in lesson.sections)
    # Les positions sont ordonnées sans trou — l'affichage s'appuie dessus.
    assert [s.position for s in lesson.sections] == list(range(len(lesson.sections)))


def test_import_signale_un_pdf_sans_texte_extractible(db_session):
    """ACQUIS — un PDF sans couche de texte (cas du document scanné, §37) doit
    produire un avertissement explicite plutôt qu'un échec silencieux."""
    db_session.add(School(id="pdf-empty-school", name="École", short_name="PDF", color="#000000"))
    db_session.commit()

    from tests.pdf_fixtures import build_pdf

    empty_pdf = build_pdf([[]])  # une page, aucun texte
    _course, _lesson, page_count, warning = PdfImportService(db_session).import_pdf(
        file_bytes=empty_pdf, filename="scan.pdf", school_id="pdf-empty-school",
    )

    assert page_count == 1
    assert warning is not None
    assert "scanné" in warning
