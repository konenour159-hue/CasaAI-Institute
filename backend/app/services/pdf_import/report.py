"""
Rapport de qualité d'un import (§28, §34, §37, §44).

Le moteur prend une longue suite de décisions dont beaucoup sont
probabilistes. Sans restitution, un import mal découpé reste inexplicable et
l'utilisateur n'a aucun moyen de savoir ce qui mérite une relecture.

Le rapport répond à trois besoins distincts :

- **compter** ce qui a été produit, pour situer un import d'un coup d'œil ;
- **signaler** ce dont le moteur n'est pas sûr, plutôt que de le passer sous
  silence (§14 : un élément ambigu ne doit jamais être présenté comme
  certain) ;
- **détecter** les cas où le résultat ne veut rien dire — au premier rang
  desquels le PDF scanné (§37), qu'il faut annoncer comme tel plutôt que de
  livrer une structure vide.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.pdf_import.blocks import (
    CAPTION_BLOCK,
    CODE_BLOCK,
    FORMULA_BLOCK,
    LIST_BLOCK,
    TABLE_BLOCK,
    Element,
)
from app.services.pdf_import.classifier import Classification, HEADING, UNKNOWN
from app.services.pdf_import.hierarchy import Section, flatten
from app.services.pdf_import.margins import MarginReport
from app.services.pdf_import.models import Page, Paragraph

logger = logging.getLogger("casa.pdf_import")

# Types de document (§37).
TEXT_DOCUMENT = "TEXT"
SCANNED_DOCUMENT = "SCANNED"

# En dessous de cette part de pages porteuses de texte, l'extraction n'a rien
# donné d'exploitable et le document est très probablement scanné.
_SCANNED_THRESHOLD = 0.2

# Un bloc nettement plus long que les autres trahit en général une frontière
# manquée. Seuil en caractères, volontairement large pour ne signaler que les
# cas francs.
_OVERSIZED_BLOCK = 6000


@dataclass
class Anomaly:
    """Point à vérifier, avec de quoi le retrouver dans le PDF d'origine."""

    kind: str
    message: str
    page: int | None = None
    confidence: float | None = None


@dataclass
class QualityReport:
    pages: int = 0
    sections: int = 0
    subsections: int = 0
    headings: int = 0
    paragraphs: int = 0
    blocks: int = 0
    lists: int = 0
    code_blocks: int = 0
    tables: int = 0
    formulas: int = 0
    captions: int = 0
    boilerplate_removed: int = 0
    multi_column_pages: int = 0
    average_confidence: float = 0.0
    document_type: str = TEXT_DOCUMENT
    text_extraction_confidence: float = 1.0
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def needs_review(self) -> int:
        return len(self.anomalies)

    def to_dict(self) -> dict:
        return {
            "pages": self.pages,
            "sections": self.sections,
            "subsections": self.subsections,
            "headings": self.headings,
            "paragraphs": self.paragraphs,
            "blocks": self.blocks,
            "lists": self.lists,
            "code_blocks": self.code_blocks,
            "tables": self.tables,
            "formulas": self.formulas,
            "captions": self.captions,
            "boilerplate_removed": self.boilerplate_removed,
            "multi_column_pages": self.multi_column_pages,
            "average_confidence": round(self.average_confidence, 3),
            "document_type": self.document_type,
            "text_extraction_confidence": round(self.text_extraction_confidence, 3),
            "anomalies": [
                {
                    "kind": anomaly.kind,
                    "message": anomaly.message,
                    "page": anomaly.page,
                    "confidence": round(anomaly.confidence, 2) if anomaly.confidence is not None else None,
                }
                for anomaly in self.anomalies
            ],
        }


def _extraction_confidence(pages: list[Page]) -> float:
    if not pages:
        return 0.0
    with_text = sum(1 for page in pages if page.lines)
    return with_text / len(pages)


def build_report(
    *,
    pages: list[Page],
    paragraphs: list[Paragraph],
    classifications: list[Classification],
    elements: list[Element],
    roots: list[Section],
    margins: MarginReport | None = None,
) -> QualityReport:
    """Assemble le rapport à partir des artefacts de la chaîne."""
    report = QualityReport(pages=len(pages), paragraphs=len(paragraphs))
    report.text_extraction_confidence = _extraction_confidence(pages)
    report.multi_column_pages = sum(1 for page in pages if page.column_count > 1)

    if margins is not None:
        report.boilerplate_removed = margins.total

    flat = flatten(roots)
    report.sections = sum(1 for section in flat if section.level == 1)
    report.subsections = sum(1 for section in flat if section.level > 1)
    report.headings = sum(1 for result in classifications if result.type == HEADING)

    blocks = [element.block for element in elements if element.kind == "BLOCK" and element.block]
    report.blocks = len(blocks)
    report.lists = sum(1 for block in blocks if block.kind == LIST_BLOCK)
    report.code_blocks = sum(1 for block in blocks if block.kind == CODE_BLOCK)
    report.tables = sum(1 for block in blocks if block.kind == TABLE_BLOCK)
    report.formulas = sum(1 for block in blocks if block.kind == FORMULA_BLOCK)
    report.captions = sum(1 for block in blocks if block.kind == CAPTION_BLOCK)

    if classifications:
        report.average_confidence = sum(r.confidence for r in classifications) / len(classifications)

    # --- Anomalies ---------------------------------------------------------

    # PDF scanné : à annoncer d'emblée, tout le reste du rapport perdant son
    # sens dans ce cas.
    if report.text_extraction_confidence < _SCANNED_THRESHOLD:
        report.document_type = SCANNED_DOCUMENT
        report.anomalies.append(Anomaly(
            "SCANNED_DOCUMENT",
            "Extraction textuelle insuffisante : ce PDF est probablement scanné. "
            "L'OCR n'est pas pris en charge.",
            confidence=report.text_extraction_confidence,
        ))
        return report

    for paragraph, result in zip(paragraphs, classifications):
        if result.type == HEADING and result.is_ambiguous:
            report.anomalies.append(Anomaly(
                "AMBIGUOUS_HEADING",
                f"Titre incertain : « {paragraph.text[:70]} »",
                page=paragraph.page_start if paragraph.page_start >= 0 else None,
                confidence=result.confidence,
            ))
        elif result.type == UNKNOWN:
            report.anomalies.append(Anomaly(
                "UNKNOWN_ELEMENT",
                f"Élément non classé : « {paragraph.text[:70]} »",
                page=paragraph.page_start if paragraph.page_start >= 0 else None,
                confidence=result.confidence,
            ))

    # Un tableau sans en-tête reconnu reste utilisable, mais l'utilisateur
    # doit savoir que la première ligne n'a pas été distinguée des autres
    # plutôt que de croire à un tableau sans en-tête (§22, règle 8).
    for block in blocks:
        if block.kind == TABLE_BLOCK and block.table is not None and block.table.headers is None:
            report.anomalies.append(Anomaly(
                "TABLE_WITHOUT_HEADERS",
                f"Tableau de {len(block.table.rows)} lignes sans ligne d'en-tête identifiable : "
                "toutes les lignes sont livrées comme des données.",
                page=block.page_start if block.page_start >= 0 else None,
                confidence=block.table.confidence,
            ))

    for block in blocks:
        if len(block.text) > _OVERSIZED_BLOCK:
            report.anomalies.append(Anomaly(
                "OVERSIZED_BLOCK",
                f"Bloc anormalement long ({len(block.text)} caractères) : une frontière "
                "de paragraphe a probablement été manquée.",
                page=block.page_start if block.page_start >= 0 else None,
            ))

    # Le réordonnancement en colonnes change l'ordre du texte : c'est la
    # décision du moteur qui a le plus d'effet sur le résultat, et un tableau
    # à deux colonnes peut encore être pris pour une mise en colonnes. À
    # signaler, donc, même quand tout s'est bien passé.
    if report.multi_column_pages:
        report.anomalies.append(Anomaly(
            "MULTI_COLUMN",
            f"{report.multi_column_pages} page(s) lue(s) en colonnes : le texte a été "
            "réordonné colonne par colonne. À vérifier si le document contient des tableaux.",
        ))

    empty_pages = sum(1 for page in pages if not page.lines)
    if empty_pages:
        report.anomalies.append(Anomaly(
            "EMPTY_PAGES",
            f"{empty_pages} page(s) sans texte extractible, ignorée(s).",
        ))

    # Un document dépourvu de titre n'est pas une erreur en soi (règle 8 : ne
    # rien inventer), mais mérite d'être signalé : la structure produite se
    # réduira à une seule section.
    if not report.headings and report.paragraphs:
        report.anomalies.append(Anomaly(
            "NO_HEADINGS",
            "Aucun titre détecté : le document est livré en une seule section.",
        ))

    return report


def log_report(report: QualityReport, *, filename: str) -> None:
    """Journal structuré des étapes (§44)."""
    logger.info("[PDF] %s : %d pages extraites", filename, report.pages)
    logger.info("[COLUMNS] %d page(s) lue(s) en colonnes", report.multi_column_pages)
    logger.info("[MARGINS] %d éléments d'en-tête/pied écartés", report.boilerplate_removed)
    logger.info("[PARAGRAPH] %d paragraphes reconstruits", report.paragraphs)
    logger.info("[HEADING] %d titres détectés", report.headings)
    logger.info("[STRUCTURE] %d sections, %d sous-sections", report.sections, report.subsections)
    logger.info(
        "[SEGMENT] %d blocs (%d listes, %d code, %d tableaux, %d formules, %d légendes)",
        report.blocks, report.lists, report.code_blocks, report.tables,
        report.formulas, report.captions,
    )
    logger.info(
        "[VALIDATION] confiance moyenne %.2f, %d point(s) à vérifier",
        report.average_confidence, report.needs_review,
    )
