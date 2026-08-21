"""
Lecture de la structure documentaire côté apprenant — phase Q, option B.

Le modèle plat rend le corps d'une section en un seul bloc de texte : listes,
code, tableaux et formules y perdent leur nature, alors que le moteur d'import
les a bel et bien reconnus. Ces tests couvrent la route qui expose l'arbre, et
surtout la coexistence : les 91 leçons écrites à la main n'ont aucun document
et doivent continuer de fonctionner exactement comme avant.
"""
from __future__ import annotations

from app.core.security import create_access_token
from app.models.catalog import School
from app.models.content import Course, Lesson, LessonSection
from app.models.enums import ContentStatus, UserRole
from app.repositories.user_repository import UserRepository
from app.services.pdf_import_service import PdfImportService
from tests.pdf_fixtures import ALL_FIXTURES


def _headers(client, db_session, email: str) -> dict:
    client.post("/api/auth/register", json={
        "first_name": "Ada", "last_name": "Lovelace", "email": email,
        "password": "SuperSecret123!",
    })
    user = UserRepository(db_session).get_by_email(email)
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def _imported_lesson(db_session, school_id: str, fixture: str = "nested_headings"):
    db_session.add(School(id=school_id, name="École", short_name="T", color="#000000"))
    db_session.commit()
    result = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES[fixture](), filename="cours-de-donnees.pdf", school_id=school_id,
    )
    # Une leçon n'est lisible par un apprenant qu'une fois publiée ; l'import
    # la dépose en brouillon, comme il se doit.
    result.course.status = ContentStatus.PUBLISHED
    result.lesson.status = ContentStatus.PUBLISHED
    db_session.commit()
    return result


def _handwritten_lesson(db_session, school_id: str) -> str:
    db_session.add(School(id=school_id, name="École", short_name="T", color="#000000"))
    db_session.add(Course(id=f"c-{school_id}", school_id=school_id, title="Écrit à la main",
                          status=ContentStatus.PUBLISHED))
    db_session.add(Lesson(id=f"l-{school_id}", course_id=f"c-{school_id}", title="Leçon manuelle",
                          position=0, status=ContentStatus.PUBLISHED))
    db_session.add(LessonSection(lesson_id=f"l-{school_id}", position=0,
                                 title="Définition", body="Une donnée est une observation."))
    db_session.commit()
    return f"l-{school_id}"


# --- Coexistence des deux modèles -------------------------------------------

def test_une_lecon_ecrite_a_la_main_n_annonce_aucun_document(client, db_session):
    lesson_id = _handwritten_lesson(db_session, "doc-main")
    headers = _headers(client, db_session, "doc-main@example.com")

    detail = client.get(f"/api/lessons/{lesson_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["has_document"] is False
    # Et son contenu plat est intact : c'est tout l'enjeu de la coexistence.
    assert detail.json()["sections"][0]["title"] == "Définition"

    assert client.get(f"/api/lessons/{lesson_id}/document", headers=headers).status_code == 404


def test_une_lecon_importee_annonce_son_document(client, db_session):
    result = _imported_lesson(db_session, "doc-import")
    headers = _headers(client, db_session, "doc-import@example.com")

    detail = client.get(f"/api/lessons/{result.lesson.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["has_document"] is True
    # Les sections plates restent servies : l'affichage de repli ne bouge pas.
    assert detail.json()["sections"]


# --- L'arbre servi ----------------------------------------------------------

def test_l_arbre_est_servi_avec_sa_source(client, db_session):
    result = _imported_lesson(db_session, "doc-arbre")
    headers = _headers(client, db_session, "doc-arbre@example.com")

    resp = client.get(f"/api/lessons/{result.lesson.id}/document", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_file"] == "cours-de-donnees.pdf"
    assert body["page_count"] == 1

    titres = [section["title"] for section in body["sections"]]
    assert "1. Donnees" in titres
    donnees = next(s for s in body["sections"] if s["title"] == "1. Donnees")
    assert [child["title"] for child in donnees["children"]] == [
        "1.1 Donnees structurees", "1.2 Donnees non structurees",
    ]


def test_les_blocs_gardent_leur_nature(client, db_session):
    """Ce que l'affichage plat perdait : une liste redevenait du texte."""
    result = _imported_lesson(db_session, "doc-listes", fixture="lists")
    headers = _headers(client, db_session, "doc-listes@example.com")

    body = client.get(f"/api/lessons/{result.lesson.id}/document", headers=headers).json()

    def walk(sections):
        for section in sections:
            yield from section["blocks"]
            yield from walk(section["children"])

    blocks = list(walk(body["sections"]))
    listes = [block for block in blocks if block["kind"] == "LIST"]
    assert listes, "la liste doit arriver jusqu'au client comme une liste"
    assert any("Python" in item for item in listes[0]["items"])


def test_les_blocs_gardent_leur_provenance(client, db_session):
    """§26 : de quelle page vient ce que l'apprenant lit."""
    result = _imported_lesson(db_session, "doc-pages", fixture="complex_course")
    headers = _headers(client, db_session, "doc-pages@example.com")

    body = client.get(f"/api/lessons/{result.lesson.id}/document", headers=headers).json()

    def walk(sections):
        for section in sections:
            yield from section["blocks"]
            yield from walk(section["children"])

    assert any(block["page_start"] is not None for block in walk(body["sections"]))


# --- Accès ------------------------------------------------------------------

def test_le_document_demande_une_authentification(client, db_session):
    result = _imported_lesson(db_session, "doc-auth")
    resp = client.get(f"/api/lessons/{result.lesson.id}/document")
    assert resp.status_code in (401, 403)


def test_une_lecon_inconnue_repond_404(client, db_session):
    headers = _headers(client, db_session, "doc-404@example.com")
    assert client.get("/api/lessons/inconnue/document", headers=headers).status_code == 404
