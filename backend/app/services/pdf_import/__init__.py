"""
Moteur d'import PDF — restructuration en cours (cahier technique dédié).

Étape atteinte : extraction enrichie et modèle intermédiaire. Ce paquet est
pour l'instant **autonome** : `services/pdf_import_service.py` continue de
produire les sections d'un import et n'en dépend pas encore. Le branchement
se fera une fois la chaîne complète (classification, hiérarchie,
segmentation) constituée et comparée à l'existant.
"""
from app.services.pdf_import.blocks import (
    CAPTION_BLOCK,
    CODE_BLOCK,
    FORMULA_BLOCK,
    LIST_BLOCK,
    TABLE_BLOCK,
    TEXT_BLOCK,
    Block,
    Element,
    segment,
    should_start_new_block,
)
from app.services.pdf_import.classifier import (
    CAPTION,
    CODE,
    FORMULA,
    HEADING,
    LIST_ITEM,
    PARAGRAPH,
    TABLE_ROW,
    UNKNOWN,
    Classification,
    classify,
    classify_all,
)
from app.services.pdf_import.columns import (
    Column,
    ColumnLayout,
    ReadingGroup,
    detect_columns,
    sort_reading_order,
)
from app.services.pdf_import.extractor import extract_pages
from app.services.pdf_import.hierarchy import Section, assign_levels, build_tree, flatten
from app.services.pdf_import.layout import attach_lines, body_font_size, group_lines
from app.services.pdf_import.margins import (
    MarginReport,
    analyze_margins,
    content_lines,
    looks_like_page_number,
)
from app.services.pdf_import.models import Fragment, Line, Page, Paragraph
from app.services.pdf_import.report import Anomaly, QualityReport, build_report, log_report
from app.services.pdf_import.normalizer import join_lines, normalize_text
from app.services.pdf_import.paragraphs import group_paragraphs, median_leading
from app.services.pdf_import.tables import Cell, Table, detect_tables, split_cells

__all__ = [
    "Fragment",
    "Line",
    "Page",
    "Paragraph",
    "extract_pages",
    "group_lines",
    "attach_lines",
    "body_font_size",
    "Column",
    "ColumnLayout",
    "ReadingGroup",
    "detect_columns",
    "sort_reading_order",
    "normalize_text",
    "join_lines",
    "group_paragraphs",
    "median_leading",
    "analyze_margins",
    "content_lines",
    "looks_like_page_number",
    "MarginReport",
    "classify",
    "classify_all",
    "Classification",
    "Block",
    "Element",
    "segment",
    "should_start_new_block",
    "TEXT_BLOCK",
    "LIST_BLOCK",
    "CODE_BLOCK",
    "CAPTION_BLOCK",
    "TABLE_BLOCK",
    "FORMULA_BLOCK",
    "HEADING",
    "PARAGRAPH",
    "CODE",
    "LIST_ITEM",
    "TABLE_ROW",
    "FORMULA",
    "CAPTION",
    "UNKNOWN",
    "Table",
    "Cell",
    "detect_tables",
    "split_cells",
    "Section",
    "build_tree",
    "assign_levels",
    "flatten",
    "build_report",
    "log_report",
    "QualityReport",
    "Anomaly",
]
