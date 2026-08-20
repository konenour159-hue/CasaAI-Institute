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
from app.services.pdf_import.models import Fragment, Line, Page

__all__ = [
    "Fragment",
    "Line",
    "Page",
    "extract_pages",
    "group_lines",
    "attach_lines",
    "body_font_size",
]
