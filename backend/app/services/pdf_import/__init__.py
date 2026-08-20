"""
Moteur d'import PDF — restructuration en cours (cahier technique dédié).

Étape atteinte : extraction enrichie et modèle intermédiaire. Ce paquet est
pour l'instant **autonome** : `services/pdf_import_service.py` continue de
produire les sections d'un import et n'en dépend pas encore. Le branchement
se fera une fois la chaîne complète (classification, hiérarchie,
segmentation) constituée et comparée à l'existant.
"""
from app.services.pdf_import.extractor import extract_pages
from app.services.pdf_import.layout import attach_lines, body_font_size, group_lines
from app.services.pdf_import.margins import (
    MarginReport,
    analyze_margins,
    content_lines,
    looks_like_page_number,
)
from app.services.pdf_import.models import Fragment, Line, Page, Paragraph
from app.services.pdf_import.normalizer import join_lines, normalize_text
from app.services.pdf_import.paragraphs import group_paragraphs, median_leading

__all__ = [
    "Fragment",
    "Line",
    "Page",
    "Paragraph",
    "extract_pages",
    "group_lines",
    "attach_lines",
    "body_font_size",
    "normalize_text",
    "join_lines",
    "group_paragraphs",
    "median_leading",
    "analyze_margins",
    "content_lines",
    "looks_like_page_number",
    "MarginReport",
]
