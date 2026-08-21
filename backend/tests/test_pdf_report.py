"""
Rapport de qualité d'un import — §28, §34, §37.

Le moteur enchaîne des décisions probabilistes. Sans restitution, un import
mal découpé reste inexplicable et rien n'indique ce qui mérite une relecture.
Le rapport compte ce qui a été produit, signale ce dont le moteur n'est pas
sûr, et détecte les cas où le résultat n'a pas de sens — au premier rang
desquels le PDF scanné.
"""
from __future__ import annotations

from app.models.catalog import School
from app.services.pdf_import import (
    analyze_margins,
    attach_lines,
    body_font_size,
    build_report,
    build_tree,
    classify_all,
    extract_pages,
    group_paragraphs,
    merge_overline_headings,
    segment,
)
from app.services.pdf_import.report import SCANNED_DOCUMENT, TEXT_DOCUMENT
from app.services.pdf_import_service import PdfImportService
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def report_of(pdf_bytes: bytes):
    pages = attach_lines(extract_pages(pdf_bytes))
    body = body_font_size(pages)
    margins = analyze_margins(pages, body)
    paragraphs = group_paragraphs(pages)
    classifications = classify_all(paragraphs, body)
    paragraphs, classifications = merge_overline_headings(paragraphs, classifications)
    elements = segment(paragraphs, classifications)
    roots = build_tree(elements)
    return build_report(
        pages=pages, paragraphs=paragraphs, classifications=classifications,
        elements=elements, roots=roots, margins=margins,
    )


# --- Compteurs ---------------------------------------------------------------

def test_le_rapport_compte_la_structure_produite():
    report = report_of(ALL_FIXTURES["nested_headings"]())
    assert report.pages == 1
    assert report.sections >= 1
    assert report.subsections >= 1
    assert report.headings >= 3
    assert report.paragraphs > 0
    assert report.blocks > 0
    assert report.document_type == TEXT_DOCUMENT


def test_le_rapport_distingue_les_natures_de_bloc():
    report = report_of(ALL_FIXTURES["code"]())
    assert report.code_blocks >= 1

    report = report_of(ALL_FIXTURES["lists"]())
    assert report.lists >= 1


def test_confiance_moyenne_dans_les_bornes():
    report = report_of(ALL_FIXTURES["nested_headings"]())
    assert 0.0 < report.average_confidence <= 1.0


def test_les_elements_de_marge_ecartes_sont_comptes():
    pages_spec = []
    for n in range(1, 6):
        lines = [Line("En-tete du document", x=72, y=750, size=8)]
        y = 700
        for i in range(5):
            lines.append(Line(f"Ligne {i} de contenu de la page {n}.", x=72, y=y, size=11))
            y -= 17
        lines.append(Line(str(n), x=300, y=30, size=8))
        pages_spec.append(lines)

    report = report_of(build_pdf(pages_spec))
    assert report.boilerplate_removed > 0


# --- Anomalies (§28) ---------------------------------------------------------

def test_un_titre_incertain_est_signale():
    """§14 : un élément ambigu ne doit jamais être présenté comme certain."""
    # Aucun avantage de taille sur le corps : seule la graisse plaide pour un
    # titre, ce qui place le score dans la zone grise (50-69) plutôt que de
    # trancher.
    pdf = build_pdf([[
        Line("Contexte General", x=72, y=700, size=11, font="bold"),
        Line("Le texte courant suit immediatement, sans grande", x=72, y=676, size=11),
        Line("difference typographique avec ce qui precede.", x=72, y=659, size=11),
    ]])
    report = report_of(pdf)

    assert report.headings == 1
    ambiguous = [a for a in report.anomalies if a.kind == "AMBIGUOUS_HEADING"]
    assert ambiguous, "un titre au score intermédiaire doit être remonté"
    assert "Contexte General" in ambiguous[0].message
    assert ambiguous[0].confidence is not None and ambiguous[0].confidence < 0.6


def test_un_document_sans_titre_est_signale():
    """Ce n'est pas une erreur (règle 8 : ne rien inventer), mais l'utilisateur
    doit savoir que la structure se réduira à une seule section."""
    report = report_of(ALL_FIXTURES["no_headings"]())
    assert report.headings == 0
    assert "NO_HEADINGS" in {anomaly.kind for anomaly in report.anomalies}


def test_un_pdf_sans_texte_est_declare_scanne():
    """§37 : ne pas prétendre avoir structuré un document scanné."""
    report = report_of(build_pdf([[], [], []]))
    assert report.document_type == SCANNED_DOCUMENT
    assert report.text_extraction_confidence < 0.2
    anomaly = next(a for a in report.anomalies if a.kind == "SCANNED_DOCUMENT")
    assert "scanné" in anomaly.message


def test_les_anomalies_situent_la_page_concernee():
    """§34 : pouvoir retrouver dans le PDF ce qui pose question."""
    report = report_of(ALL_FIXTURES["complex_course"]())
    for anomaly in report.anomalies:
        assert anomaly.kind
        assert anomaly.message
        if anomaly.page is not None:
            assert anomaly.page >= 0


# --- Sérialisation et remontée à l'API ---------------------------------------

def test_le_rapport_est_serialisable():
    report = report_of(ALL_FIXTURES["nested_headings"]())
    data = report.to_dict()
    assert set(data) >= {
        "pages", "sections", "subsections", "headings", "paragraphs",
        "blocks", "lists", "average_confidence", "document_type", "anomalies",
    }
    assert isinstance(data["anomalies"], list)


def test_l_import_remonte_le_rapport(db_session):
    db_session.add(School(id="report-1", name="École", short_name="R", color="#000000"))
    db_session.commit()

    report = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES["nested_headings"](), filename="cours.pdf", school_id="report-1",
    ).report
    assert report is not None
    assert report.pages == 1
    assert report.headings >= 3
    assert report.to_dict()["document_type"] == TEXT_DOCUMENT


def test_le_rapport_vaut_none_si_la_reconstruction_echoue(db_session, monkeypatch):
    """Le rapport est un enrichissement : son absence ne casse rien."""
    db_session.add(School(id="report-2", name="École", short_name="R", color="#000000"))
    db_session.commit()

    def boom(_file_bytes):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr("app.services.pdf_import_service._build_document_structure", boom)

    result = PdfImportService(db_session).import_pdf(
        file_bytes=ALL_FIXTURES["simple_course"](), filename="cours.pdf", school_id="report-2",
    )
    assert result.report is None
    assert result.lesson.sections, "l'import aboutit malgré tout"
