"""
Prévisualisation avant validation — §29, phase O.

L'import créait un cours en brouillon dès l'envoi du fichier : impossible de
voir ce que le moteur avait compris avant que ce soit écrit en base. Ces tests
tiennent les deux exigences de cette étape :

- la prévisualisation ne crée **rien** ;
- elle montre exactement ce que l'import produirait, faute de quoi valider ce
  qu'on a vu ne veut rien dire.
"""
from __future__ import annotations

from app.models.content import Course, Lesson
from app.models.document import DocumentSection
from app.services.pdf_import_service import preview_pdf
from tests.pdf_fixtures import ALL_FIXTURES


def _preview(name: str = "nested_headings", filename: str = "cours-de-donnees.pdf"):
    return preview_pdf(file_bytes=ALL_FIXTURES[name](), filename=filename)


# --- Ne rien écrire ---------------------------------------------------------

def test_la_previsualisation_ne_cree_rien(db_session):
    """Le point entier de l'étape : regarder sans engager."""
    avant = (
        db_session.query(Course).count(),
        db_session.query(Lesson).count(),
        db_session.query(DocumentSection).count(),
    )
    _preview()
    apres = (
        db_session.query(Course).count(),
        db_session.query(Lesson).count(),
        db_session.query(DocumentSection).count(),
    )
    assert avant == apres


# --- Montrer ce que l'import produirait -------------------------------------

def test_la_previsualisation_rend_l_arbre_complet():
    _title, _pages, _report, roots = _preview()
    titres = [root.title for root in roots]
    assert "1. Donnees" in titres

    donnees = next(root for root in roots if root.title == "1. Donnees")
    assert [child.title for child in donnees.children] == [
        "1.1 Donnees structurees", "1.2 Donnees non structurees",
    ]
    assert donnees.children[0].children[0].title == "1.1.1 Bases relationnelles"


def test_la_previsualisation_rend_les_compteurs_et_les_points_a_verifier():
    """Le §29 décrit un écran de chiffres : pages, sections, blocs, et le
    nombre d'éléments qui méritent une relecture."""
    _title, pages, report, _roots = _preview()
    assert pages == 1
    assert report["sections"] >= 1
    assert report["blocks"] >= 1
    assert "anomalies" in report


def test_le_titre_est_celui_que_l_import_donnerait():
    title, _pages, _report, _roots = _preview(filename="cours-de-donnees.pdf")
    assert title == "Cours De Donnees"


def test_la_previsualisation_correspond_a_l_import(db_session):
    """Sans cette égalité, valider ce qu'on a vu n'a aucun sens."""
    from app.models.catalog import School
    from app.repositories.document_structure_repository import DocumentStructureRepository
    from app.services.pdf_import_service import PdfImportService

    db_session.add(School(id="preview-1", name="École", short_name="T", color="#000000"))
    db_session.commit()

    _title, _pages, report, roots = _preview()
    _course, lesson, _count, _warning, imported = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES["nested_headings"](), filename="cours-de-donnees.pdf",
        school_id="preview-1",
    )

    assert report == imported.to_dict()
    persistees = DocumentStructureRepository(db_session).get_tree(lesson.id)
    assert [root.title for root in persistees] == [root.title for root in roots]


def test_un_pdf_illisible_est_signale():
    import pytest

    from app.services.pdf_import_service import PdfExtractionError

    with pytest.raises(PdfExtractionError):
        preview_pdf(file_bytes=b"ceci n'est pas un PDF", filename="casse.pdf")


# --- L'endpoint -------------------------------------------------------------

def _admin_headers(client, db_session) -> dict:
    from app.core.security import create_access_token
    from app.models.enums import UserRole
    from app.repositories.user_repository import UserRepository

    client.post("/api/auth/register", json={
        "first_name": "Ada", "last_name": "Lovelace",
        "email": "preview-admin@example.com", "password": "SuperSecret123!",
    })
    user = UserRepository(db_session).get_by_email("preview-admin@example.com")
    user.role = UserRole.ADMIN
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def test_l_endpoint_rend_l_arbre_et_le_rapport(client, db_session):
    headers = _admin_headers(client, db_session)
    resp = client.post(
        "/api/admin/courses/preview-pdf",
        headers=headers,
        files={"file": ("cours-de-donnees.pdf", ALL_FIXTURES["nested_headings"](), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Cours De Donnees"
    assert body["pages"] == 1
    assert body["report"]["sections"] >= 1

    titres = [section["title"] for section in body["sections"]]
    assert "1. Donnees" in titres
    donnees = next(s for s in body["sections"] if s["title"] == "1. Donnees")
    assert [child["title"] for child in donnees["children"]] == [
        "1.1 Donnees structurees", "1.2 Donnees non structurees",
    ]


def test_l_endpoint_refuse_un_fichier_qui_n_est_pas_un_pdf(client, db_session):
    headers = _admin_headers(client, db_session)
    resp = client.post(
        "/api/admin/courses/preview-pdf",
        headers=headers,
        files={"file": ("notes.txt", b"du texte", "text/plain")},
    )
    assert resp.status_code == 422


def test_l_endpoint_est_reserve_aux_administrateurs(client):
    resp = client.post(
        "/api/admin/courses/preview-pdf",
        files={"file": ("cours.pdf", ALL_FIXTURES["simple_course"](), "application/pdf")},
    )
    assert resp.status_code in (401, 403)
