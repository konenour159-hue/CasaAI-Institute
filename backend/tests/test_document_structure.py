"""
Persistance de la structure documentaire — option B.

Les tables document_sections et content_blocks s'ajoutent à côté de
lesson_sections, qui reste inchangée. Ces tests vérifient les deux faces de
cette décision : l'arbre est bien écrit avec sa hiérarchie et sa traçabilité,
*et* le contenu plat des leçons continue d'être produit à l'identique
(§48, critère 18).
"""
from __future__ import annotations

from app.models.catalog import School
from app.models.document import ContentBlock, DocumentSection, ImportedDocument
from app.repositories.document_structure_repository import DocumentStructureRepository
from app.services.pdf_import_service import PdfImportService, _build_document_structure
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def _school(db_session, school_id: str) -> None:
    db_session.add(School(id=school_id, name="École", short_name="T", color="#000000"))
    db_session.commit()


def _import(db_session, school_id: str, pdf: bytes, filename: str = "cours.pdf"):
    return PdfImportService(db_session).import_pdf(
        file_bytes=pdf, filename=filename, school_id=school_id,
    )


# --- Écriture de l'arbre -----------------------------------------------------

def test_l_import_ecrit_l_arbre_documentaire(db_session):
    _school(db_session, "struct-1")
    result = _import(
        db_session, "struct-1", ALL_FIXTURES["nested_headings"]()
    )

    roots = DocumentStructureRepository(db_session).get_tree(result.document.id)
    assert roots, "l'arbre doit être persisté"

    titles = [root.title for root in roots]
    assert "1. Donnees" in titles
    assert "2. Intelligence artificielle" in titles

    donnees = next(r for r in roots if r.title == "1. Donnees")
    assert donnees.level == 1
    assert donnees.parent_id is None

    enfants = {child.title: child for child in donnees.children}
    assert "1.1 Donnees structurees" in enfants
    structurees = enfants["1.1 Donnees structurees"]
    assert structurees.level == 2
    assert structurees.parent_id == donnees.id
    assert [petit.title for petit in structurees.children] == ["1.1.1 Bases relationnelles"]


def test_les_blocs_sont_rattaches_a_leur_section(db_session):
    _school(db_session, "struct-2")
    result = _import(
        db_session, "struct-2", ALL_FIXTURES["nested_headings"]()
    )

    blocks = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.document_id == result.document.id)
        .all()
    )
    assert blocks
    assert all(block.kind for block in blocks)
    assert all(0.0 <= block.confidence <= 1.0 for block in blocks)
    assert any("matiere premiere" in block.text for block in blocks)


def test_la_liste_conserve_ses_items(db_session):
    """§21 : une liste ne doit pas être aplatie en texte."""
    _school(db_session, "struct-3")
    result = _import(db_session, "struct-3", ALL_FIXTURES["lists"]())

    lists = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.document_id == result.document.id, ContentBlock.kind == "LIST")
        .all()
    )
    assert lists
    items = [item for block in lists for item in (block.items or [])]
    assert any("Python" in item for item in items)


def test_la_tracabilite_est_persistee(db_session):
    """§26 et §45 : chaque bloc doit garder sa provenance."""
    _school(db_session, "struct-4")
    result = _import(
        db_session, "struct-4", ALL_FIXTURES["complex_course"]()
    )

    blocks = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.document_id == result.document.id)
        .all()
    )
    assert blocks
    traced = [b for b in blocks if b.source]
    assert traced, "au moins un bloc doit porter sa provenance"

    source = traced[0].source
    assert source["line_count"] >= 1
    assert source["lines"]
    assert "page" in source["lines"][0]
    assert traced[0].page_start is not None


# --- Non-régression : l'existant ne bouge pas --------------------------------

def test_les_sections_plates_de_la_lecon_restent_produites(db_session):
    """Le cœur de l'option B : l'affichage actuel ne doit rien perdre."""
    _school(db_session, "struct-5")
    result = _import(
        db_session, "struct-5", ALL_FIXTURES["nested_headings"]()
    )

    assert result.lesson.sections, "les sections plates existent toujours"
    assert [s.position for s in result.lesson.sections] == list(range(len(result.lesson.sections)))
    assert all(s.title and s.body for s in result.lesson.sections)
    assert any("Donnees" in s.title for s in result.lesson.sections)


def test_un_echec_du_nouveau_moteur_ne_casse_pas_l_import(db_session, monkeypatch):
    """Garde-fou explicite : la reconstruction est un enrichissement, jamais
    une condition de réussite de l'import."""
    _school(db_session, "struct-6")

    def boom(_file_bytes):
        raise RuntimeError("panne simulée du nouveau moteur")

    monkeypatch.setattr("app.services.pdf_import_service._build_document_structure", boom)

    result = _import(
        db_session, "struct-6", ALL_FIXTURES["simple_course"]()
    )

    assert result.lesson.sections, "l'import aboutit malgré la panne"
    assert result.page_count == 1
    assert result.warning is None
    assert DocumentStructureRepository(db_session).get_tree(result.document.id) == []


# --- Idempotence -------------------------------------------------------------

def test_reecrire_la_structure_remplace_l_ancienne(db_session):
    """Un réimport ne doit pas laisser d'anciennes sections orphelines."""
    _school(db_session, "struct-7")
    result = _import(
        db_session, "struct-7", ALL_FIXTURES["nested_headings"]()
    )
    repo = DocumentStructureRepository(db_session)
    before = db_session.query(DocumentSection).filter_by(document_id=result.document.id).count()
    assert before > 0

    roots, _report = _build_document_structure(ALL_FIXTURES["simple_course"]())
    repo.replace_for_document(result.document.id, roots)
    db_session.flush()

    after = db_session.query(DocumentSection).filter_by(document_id=result.document.id).all()
    assert after
    assert all("Donnees" not in section.title for section in after)


def test_supprimer_le_document_emporte_sa_structure(db_session):
    """La cascade doit être effective : pas de sections ni de blocs orphelins."""
    _school(db_session, "struct-8")
    result = _import(db_session, "struct-8", ALL_FIXTURES["nested_headings"]())
    document_id = result.document.id
    assert db_session.query(DocumentSection).filter_by(document_id=document_id).count() > 0

    db_session.delete(result.document)
    db_session.flush()

    assert db_session.query(DocumentSection).filter_by(document_id=document_id).count() == 0
    assert (
        db_session.query(ContentBlock)
        .join(DocumentSection, isouter=True)
        .filter(DocumentSection.id.is_(None))
        .count() == 0
    )


def test_supprimer_la_lecon_ne_detruit_pas_le_corpus(db_session):
    """Décision inverse de la précédente, et volontaire : le cours dérivé
    d'un import est un travail pédagogique, le document est une source. Jeter
    le premier ne doit pas retirer la seconde du corpus — sans quoi une
    réponse du futur RAG deviendrait incitable du jour au lendemain."""
    _school(db_session, "struct-8b")
    result = _import(db_session, "struct-8b", ALL_FIXTURES["nested_headings"]())
    document_id = result.document.id

    db_session.delete(result.lesson)
    db_session.flush()
    db_session.expire_all()

    document = db_session.query(ImportedDocument).filter_by(id=document_id).one()
    assert document.lesson_id is None
    assert db_session.query(DocumentSection).filter_by(document_id=document_id).count() > 0


def test_contrainte_de_niveau_respectee(db_session):
    """La base refuse un niveau hors de H1-H4 (§16), ce qui garantit qu'une
    erreur de reconstruction ne passe pas inaperçue."""
    _school(db_session, "struct-9")
    result = _import(
        db_session, "struct-9", ALL_FIXTURES["nested_headings"]()
    )
    sections = db_session.query(DocumentSection).filter_by(document_id=result.document.id).all()
    assert all(1 <= section.level <= 4 for section in sections)


def test_document_sans_titre_produit_une_section_d_accueil(db_session):
    """Règle 8 : ne rien inventer, mais ne rien perdre non plus."""
    _school(db_session, "struct-10")
    result = _import(
        db_session, "struct-10", ALL_FIXTURES["no_headings"]()
    )
    roots = DocumentStructureRepository(db_session).get_tree(result.document.id)
    assert len(roots) == 1
    assert roots[0].title == "Introduction"
    assert roots[0].blocks


def test_pages_d_origine_conservees_sur_un_document_multipage(db_session):
    _school(db_session, "struct-11")
    pdf = build_pdf([
        [Line("1. Premier titre", y=720, size=18, font="bold"),
         Line("Contenu commence sur la premiere page du document.", y=680, size=11)],
        [Line("et se poursuit sur la seconde page du document.", y=700, size=11)],
    ])
    result = _import(db_session, "struct-11", pdf)

    roots = DocumentStructureRepository(db_session).get_tree(result.document.id)
    section = roots[0]
    assert section.page_start == 0
    assert section.page_end == 1


def test_les_cellules_d_un_tableau_sont_persistees(db_session):
    """Le §22 demande une structure, pas du texte aplati. La colonne `items`
    est en JSONB : elle porte une liste pour une liste, un objet en-têtes /
    lignes pour un tableau. Ce test vérifie que l'aller-retour en base
    conserve bien la seconde forme."""
    _school(db_session, "struct-table")
    result = _import(
        db_session, "struct-table", ALL_FIXTURES["tables"]()
    )

    roots = DocumentStructureRepository(db_session).get_tree(result.document.id)
    blocs = [bloc for root in roots for bloc in root.blocks if bloc.kind == "TABLE"]
    assert len(blocs) == 1
    assert blocs[0].items == {
        "headers": ["Algorithme", "Usage"],
        "rows": [["KNN", "Classification"], ["KMeans", "Clustering"]],
    }


# --- Identité de la source (§45) ---------------------------------------------

def test_le_document_conserve_son_fichier_d_origine(db_session):
    """Le §45 place `source_file` en tête de ce qu'il faut garder : sans le
    nom du document, « page 42 » ne veut rien dire."""
    _school(db_session, "struct-src")
    result = _import(
        db_session, "struct-src", ALL_FIXTURES["complex_course"](), filename="deep-learning.pdf",
    )

    assert result.document.source_file == "deep-learning.pdf"
    assert result.document.title == "Deep Learning"
    assert result.document.page_count == 2
    assert result.document.school_id == "struct-src"
    assert result.document.lesson_id == result.lesson.id
    assert result.document.report["pages"] == 2


def test_l_arbre_est_retrouvable_depuis_la_lecon(db_session):
    """L'affichage part de la leçon : il doit pouvoir remonter à l'arbre sans
    connaître le document."""
    _school(db_session, "struct-lien")
    result = _import(db_session, "struct-lien", ALL_FIXTURES["nested_headings"]())

    repo = DocumentStructureRepository(db_session)
    assert repo.get_document_for_lesson(result.lesson.id).id == result.document.id
    assert [r.title for r in repo.get_tree_for_lesson(result.lesson.id)] == [
        r.title for r in repo.get_tree(result.document.id)
    ]


def test_une_lecon_ecrite_a_la_main_n_a_pas_d_arbre(db_session):
    """Les leçons rédigées à la main ne font pas partie du corpus et n'ont
    donc aucun document : la recherche doit rendre vide, pas échouer."""
    from app.models.content import Course, Lesson

    _school(db_session, "struct-main")
    db_session.add(Course(id="c-main", school_id="struct-main", title="Écrit à la main"))
    db_session.add(Lesson(id="l-main", course_id="c-main", title="Leçon manuelle", position=0))
    db_session.commit()

    repo = DocumentStructureRepository(db_session)
    assert repo.get_document_for_lesson("l-main") is None
    assert repo.get_tree_for_lesson("l-main") == []


# --- Document de référence, sans cours ---------------------------------------

def test_un_document_de_reference_ne_cree_aucun_cours(db_session):
    """Un ouvrage de 649 pages a sa place dans le corpus, aucune comme
    brouillon de leçon à relire et publier."""
    from app.models.content import Course, Lesson

    _school(db_session, "struct-ref")
    cours_avant = db_session.query(Course).count()
    lecons_avant = db_session.query(Lesson).count()

    result = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES["nested_headings"](), filename="ouvrage.pdf",
        school_id="struct-ref", create_course=False,
    )

    assert result.course is None
    assert result.lesson is None
    assert db_session.query(Course).count() == cours_avant
    assert db_session.query(Lesson).count() == lecons_avant


def test_un_document_de_reference_alimente_quand_meme_le_corpus(db_session):
    _school(db_session, "struct-ref2")
    result = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES["nested_headings"](), filename="ouvrage.pdf",
        school_id="struct-ref2", create_course=False,
    )

    assert result.document.lesson_id is None
    roots = DocumentStructureRepository(db_session).get_tree(result.document.id)
    assert [r.title for r in roots][:1] == ["1. Donnees"]
    blocks = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.document_id == result.document.id)
        .count()
    )
    assert blocks > 0


def test_un_document_de_reference_illisible_echoue_franchement(db_session, monkeypatch):
    """Quand aucun cours n'est créé, l'arbre *est* le résultat : son échec est
    celui de l'import, et le taire laisserait croire à une réussite."""
    import pytest

    from app.services.pdf_import_service import PdfExtractionError

    _school(db_session, "struct-ref3")

    def boom(_file_bytes):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr("app.services.pdf_import_service._build_document_structure", boom)

    with pytest.raises(PdfExtractionError):
        PdfImportService(db_session).import_pdf(
            file_bytes=ALL_FIXTURES["simple_course"](), filename="ouvrage.pdf",
            school_id="struct-ref3", create_course=False,
        )
