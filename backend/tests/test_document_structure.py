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
from app.models.document import ContentBlock, DocumentSection
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
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-1", ALL_FIXTURES["nested_headings"]()
    )

    roots = DocumentStructureRepository(db_session).get_tree(lesson.id)
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
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-2", ALL_FIXTURES["nested_headings"]()
    )

    blocks = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.lesson_id == lesson.id)
        .all()
    )
    assert blocks
    assert all(block.kind for block in blocks)
    assert all(0.0 <= block.confidence <= 1.0 for block in blocks)
    assert any("matiere premiere" in block.text for block in blocks)


def test_la_liste_conserve_ses_items(db_session):
    """§21 : une liste ne doit pas être aplatie en texte."""
    _school(db_session, "struct-3")
    _course, lesson, _pages, _warning, _report = _import(db_session, "struct-3", ALL_FIXTURES["lists"]())

    lists = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.lesson_id == lesson.id, ContentBlock.kind == "LIST")
        .all()
    )
    assert lists
    items = [item for block in lists for item in (block.items or [])]
    assert any("Python" in item for item in items)


def test_la_tracabilite_est_persistee(db_session):
    """§26 et §45 : chaque bloc doit garder sa provenance."""
    _school(db_session, "struct-4")
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-4", ALL_FIXTURES["complex_course"]()
    )

    blocks = (
        db_session.query(ContentBlock)
        .join(DocumentSection)
        .filter(DocumentSection.lesson_id == lesson.id)
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
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-5", ALL_FIXTURES["nested_headings"]()
    )

    assert lesson.sections, "les sections plates existent toujours"
    assert [s.position for s in lesson.sections] == list(range(len(lesson.sections)))
    assert all(s.title and s.body for s in lesson.sections)
    assert any("Donnees" in s.title for s in lesson.sections)


def test_un_echec_du_nouveau_moteur_ne_casse_pas_l_import(db_session, monkeypatch):
    """Garde-fou explicite : la reconstruction est un enrichissement, jamais
    une condition de réussite de l'import."""
    _school(db_session, "struct-6")

    def boom(_file_bytes):
        raise RuntimeError("panne simulée du nouveau moteur")

    monkeypatch.setattr("app.services.pdf_import_service._build_document_structure", boom)

    _course, lesson, pages, warning, _report = _import(
        db_session, "struct-6", ALL_FIXTURES["simple_course"]()
    )

    assert lesson.sections, "l'import aboutit malgré la panne"
    assert pages == 1
    assert warning is None
    assert DocumentStructureRepository(db_session).get_tree(lesson.id) == []


# --- Idempotence -------------------------------------------------------------

def test_reecrire_la_structure_remplace_l_ancienne(db_session):
    """Un réimport ne doit pas laisser d'anciennes sections orphelines."""
    _school(db_session, "struct-7")
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-7", ALL_FIXTURES["nested_headings"]()
    )
    repo = DocumentStructureRepository(db_session)
    before = db_session.query(DocumentSection).filter_by(lesson_id=lesson.id).count()
    assert before > 0

    roots, _report = _build_document_structure(ALL_FIXTURES["simple_course"]())
    repo.replace_for_lesson(lesson.id, roots)
    db_session.flush()

    after = db_session.query(DocumentSection).filter_by(lesson_id=lesson.id).all()
    assert after
    assert all("Donnees" not in section.title for section in after)


def test_supprimer_la_lecon_emporte_sa_structure(db_session):
    """La cascade doit être effective : pas de sections ni de blocs orphelins."""
    _school(db_session, "struct-8")
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-8", ALL_FIXTURES["nested_headings"]()
    )
    lesson_id = lesson.id
    assert db_session.query(DocumentSection).filter_by(lesson_id=lesson_id).count() > 0

    db_session.delete(lesson)
    db_session.flush()

    assert db_session.query(DocumentSection).filter_by(lesson_id=lesson_id).count() == 0
    assert (
        db_session.query(ContentBlock)
        .join(DocumentSection, isouter=True)
        .filter(DocumentSection.id.is_(None))
        .count() == 0
    )


def test_contrainte_de_niveau_respectee(db_session):
    """La base refuse un niveau hors de H1-H4 (§16), ce qui garantit qu'une
    erreur de reconstruction ne passe pas inaperçue."""
    _school(db_session, "struct-9")
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-9", ALL_FIXTURES["nested_headings"]()
    )
    sections = db_session.query(DocumentSection).filter_by(lesson_id=lesson.id).all()
    assert all(1 <= section.level <= 4 for section in sections)


def test_document_sans_titre_produit_une_section_d_accueil(db_session):
    """Règle 8 : ne rien inventer, mais ne rien perdre non plus."""
    _school(db_session, "struct-10")
    _course, lesson, _pages, _warning, _report = _import(
        db_session, "struct-10", ALL_FIXTURES["no_headings"]()
    )
    roots = DocumentStructureRepository(db_session).get_tree(lesson.id)
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
    _course, lesson, _pages, _warning, _report = _import(db_session, "struct-11", pdf)

    roots = DocumentStructureRepository(db_session).get_tree(lesson.id)
    section = roots[0]
    assert section.page_start == 0
    assert section.page_end == 1
