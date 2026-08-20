"""
Import de cours depuis un PDF (demande explicite : « ajouter des nouveaux
cours via format PDF »).

Portée V1, assumée : détection de titres et regroupement en sections par
heuristique texte (pas d'analyse de mise en page ni de police — pypdf ne
l'expose pas de façon fiable), un cours + une leçon par import, statut DRAFT
systématique — un administrateur doit relire et publier manuellement.

Le découpage suit le principe « un chunk = une idée » plutôt qu'une coupe à
taille fixe (cf. discussion de conception « Passage d'un texte à des chunks
bien ordonnés ») :

    PDF → pages → lignes → détection de titres → regroupement en sections
    ordonnées (chunks) → LessonSection

Chaque section conserve sa position d'origine (LessonSection.position, déjà
géré par AdminContentRepository) — pas besoin de dupliquer titre du cours ou
de la leçon dans chaque section, ces informations vivent déjà dans les tables
parentes (courses/lessons).

Le découpage filtre aussi deux sources de bruit identifiées sur un import
réel (rapport institutionnel avec en-tête répété et notes de bas de page
numérotées) : les lignes qui se répètent sur une part significative des
pages (en-têtes/pieds de page, cf. `_detect_repeated_boilerplate`) et les
lignes numérotées qui renvoient vers une source (« Voir... », URL — cf.
`_looks_like_footnote`), qui suivent sinon exactement le même motif texte
qu'un titre de chapitre numéroté.

Limite assumée : la détection de titres est heuristique (numérotation,
MAJUSCULES, ligne courte en tête de page) et peut se tromper sur des mises en
page atypiques (colonnes multiples, PDF scanné, titres stylés uniquement par
la police, sans numérotation ni majuscules). Vérifié empiriquement : pypdf
`extract_text()` ne restitue quasiment jamais de ligne vide entre deux
paragraphes (même quand le PDF source a un espacement visuel clair) — un
sous-titre non numéroté au milieu d'une page, sans appui typographique fort,
ne sera donc généralement pas détecté en V1 et restera fondu dans le
paragraphe. Une évolution vers un découpage sémantique réel (analyse de
sens, embeddings, base vectorielle — cf. RAG) est une étape distincte et
volontairement hors périmètre ici.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.content import Course, Lesson
from app.models.enums import ContentStatus
from app.repositories.admin_content_repository import AdminContentRepository
from app.schemas.admin import AdminCourseIn, AdminLessonIn, AdminLessonSectionIn
from app.services.admin_content_service import ValidationError


class PdfExtractionError(Exception):
    pass


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    words = re.sub(r"[_\-]+", " ", stem).strip()
    return words.title() if words else "Cours importé"


# --- Détection de titres (étape 2 : identification de la structure) --------
#
# Numérotation explicite : "1. Introduction", "1.2 Définition", "I. Contexte",
# "Chapitre 1 : ...", "Partie 2 - ...". Signal le plus fiable, aucune
# ambiguïté possible avec une phrase normale.
_NUMBERED_HEADING_RE = re.compile(
    r"^(chapitre|partie|section|module|annexe)\s+\d+\b"
    r"|^\d+(\.\d+)*[.\)]?\s+\S"
    r"|^[IVXLCDM]{1,6}[.\)]\s+\S",
    re.IGNORECASE,
)

# Mots qui, en début de ligne courte, trahissent presque toujours une phrase
# normale plutôt qu'un titre (article, préposition, conjonction) — sert à
# écarter des faux positifs sur la heuristique « ligne courte sans
# ponctuation finale ».
_LEADING_LOWERCASE_WORD_RE = re.compile(
    r"^(le|la|les|un|une|des|de|du|et|ou|mais|donc|car|ni|que|qui|dans|pour|"
    r"avec|sur|sous|par|the|a|an|and|or|but|of|in|on|for|with)\b",
    re.IGNORECASE,
)

_SENTENCE_END_RE = re.compile(r"[.!?…]$")
_MAX_HEADING_LEN = 90

# Une ligne numérotée qui renvoie vers une source ("Voir ...", "Cf. ...") ou
# contient une URL est presque toujours une note de bas de page, pas un
# titre — un rapport avec beaucoup de notes (courant dans les documents
# académiques/institutionnels) sature sinon le découpage de fausses sections
# numérotées (vérifié empiriquement, cf. import réel testé).
_FOOTNOTE_LEAD_RE = re.compile(r"^\d+(\.\d+)*[.\)]?\s+(voir\b|cf\.|source\s*:)", re.IGNORECASE)
_URL_HINT_RE = re.compile(r"https?://|www\.\w|\b\w[\w-]*\.(com|org|net|fr|io|edu)\b", re.IGNORECASE)


def _looks_like_footnote(stripped: str) -> bool:
    return bool(_FOOTNOTE_LEAD_RE.match(stripped) or _URL_HINT_RE.search(stripped))


def _detect_repeated_boilerplate(pages: list[str], *, min_page_fraction: float = 0.25, min_occurrences: int = 3) -> set[str]:
    """En-têtes/pieds de page répétés sur (presque) chaque page — ex: le titre
    du document réimprimé en haut de chaque page. Sans ce filtre, une ligne
    de ce type est détectée comme un nouveau titre à *chaque* occurrence et
    fragmente le document en dizaines de sections vides (vérifié
    empiriquement : jusqu'à 30% des sections d'un import réel). Normalisée
    (espaces/casse, chiffres neutralisés) pour tolérer un numéro de page
    variable dans une ligne par ailleurs identique."""
    counts: Counter[str] = Counter()
    for page_text in pages:
        seen_this_page: set[str] = set()
        for raw_line in page_text.split("\n"):
            line = raw_line.strip()
            if not line or len(line) > 120:
                continue
            norm = re.sub(r"\d+", "#", re.sub(r"\s+", " ", line)).strip().lower()
            if norm and norm not in seen_this_page:
                counts[norm] += 1
                seen_this_page.add(norm)

    threshold = max(min_occurrences, int(len(pages) * min_page_fraction))
    return {norm for norm, c in counts.items() if c >= threshold}


def _normalize_for_boilerplate_lookup(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip())).strip().lower()


def _is_probable_heading(line: str, *, is_first_line_of_page: bool, prev_line_blank: bool) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LEN:
        return False

    if _NUMBERED_HEADING_RE.match(stripped):
        return not _looks_like_footnote(stripped)

    letters = [c for c in stripped if c.isalpha()]
    if len(letters) >= 3 and stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return True

    # Heuristique la plus faible : ligne courte, sans ponctuation de fin de
    # phrase, qui ne commence pas par un mot de liaison — acceptée seulement
    # si elle est visuellement isolée (précédée d'une ligne vide, ou en tête
    # de page) pour limiter les faux positifs sur une simple phrase brève.
    if (
        (is_first_line_of_page or prev_line_blank)
        and len(stripped) <= 70
        and not _SENTENCE_END_RE.search(stripped)
        and not _LEADING_LOWERCASE_WORD_RE.match(stripped)
        and stripped[0].isupper()
    ):
        return True

    return False


def _chunk_pages_into_sections(pages: list[str]) -> list[tuple[str, str]]:
    """Étapes 2-5 du découpage : parcourt le document en continu (au-delà des
    frontières de page, pour ne pas couper une idée en deux comme le faisait
    l'ancienne version « une page = une section »), détecte les titres, et
    regroupe les paragraphes sous le titre courant.

    Renvoie une liste ordonnée de (titre, corps) — le corps rejoint les
    lignes d'un même paragraphe par un espace (pypdf coupe au retour à la
    ligne visuel, pas au paragraphe) et sépare les paragraphes distincts par
    une ligne vide, conservée pour l'affichage (LessonSection.body est rendu
    en `white-space: pre-line`)."""
    boilerplate = _detect_repeated_boilerplate(pages)

    sections: list[tuple[str, list[list[str]]]] = []  # (title, paragraphs[words-as-lines])
    current_paragraph: list[str] = []
    prev_line_blank = True

    def flush_paragraph() -> None:
        if current_paragraph and sections:
            sections[-1][1].append(current_paragraph.copy())
        current_paragraph.clear()

    for page_text in pages:
        # rstrip() avant découpage : pypdf termine systématiquement le texte
        # de chaque page par un retour à la ligne, qui produirait sinon une
        # ligne vide artificielle exactement à la frontière de page — et
        # couperait un paragraphe qui continue sur la page suivante (le bug
        # que ce découpage cherche justement à corriger).
        for i, raw_line in enumerate(page_text.rstrip().split("\n")):
            line = raw_line.strip()

            if not line:
                flush_paragraph()
                prev_line_blank = True
                continue

            if _normalize_for_boilerplate_lookup(line) in boilerplate:
                # En-tête/pied de page répété : complètement ignoré, ni titre
                # ni contenu — ne modifie pas prev_line_blank (une ligne
                # invisible n'isole pas visuellement ce qui suit).
                continue

            if _is_probable_heading(line, is_first_line_of_page=(i == 0), prev_line_blank=prev_line_blank):
                flush_paragraph()
                sections.append((line, []))
                prev_line_blank = False
                continue

            if not sections:
                # Contenu avant tout titre détecté (page de garde, préambule)
                # : section d'accueil neutre plutôt que de le perdre.
                sections.append(("Introduction", []))

            current_paragraph.append(line)
            prev_line_blank = False

        # Volontairement PAS de flush_paragraph() ici : une fin de page ne
        # doit pas couper un paragraphe en cours (c'est exactement le bug de
        # l'ancienne version « une page = une section »). En pratique,
        # extract_text() de pypdf ne restitue quasiment jamais de ligne vide
        # entre deux paragraphes (vérifié empiriquement) — le flux continu
        # entre pages, jusqu'au prochain titre détecté ou à une vraie ligne
        # vide, est donc le comportement le plus fiable ici.

    flush_paragraph()

    result: list[tuple[str, str]] = []
    for title, paragraphs in sections:
        body = "\n\n".join(" ".join(p) for p in paragraphs).strip()
        if body:
            result.append((title, body))
    return result


class PdfImportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminContentRepository(db)

    def import_pdf(
        self, *, file_bytes: bytes, filename: str, school_id: str
    ) -> tuple[Course, Lesson, int, str | None]:
        if not self.repo.school_exists(school_id):
            raise ValidationError(f"École '{school_id}' introuvable.")

        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            raise PdfExtractionError(f"Fichier PDF illisible : {e}") from e

        page_count = len(reader.pages)
        pages_text = [(page.extract_text() or "") for page in reader.pages]
        empty_pages = sum(1 for t in pages_text if not t.strip())

        sections = [
            AdminLessonSectionIn(title=title, body=body)
            for title, body in _chunk_pages_into_sections(pages_text)
        ]

        warning = None
        if empty_pages == page_count:
            warning = (
                "Aucun texte n'a pu être extrait — ce PDF est probablement scanné "
                "(image sans couche de texte). Une leçon vide a été créée ; l'OCR "
                "n'est pas encore pris en charge."
            )
        elif empty_pages > 0:
            warning = f"{empty_pages} page(s) sur {page_count} sans texte extractible, ignorée(s)."

        title = _title_from_filename(filename)
        summary = sections[0].body[:300] if sections else None

        course = self.repo.create_course(AdminCourseIn(
            school_id=school_id, title=title, status=ContentStatus.DRAFT,
            description=f"Importé automatiquement depuis {filename}.",
        ))

        lesson = self.repo.create_lesson(AdminLessonIn(
            course_id=course.id, title=title, status=ContentStatus.DRAFT,
            summary=summary, position=0, sections=sections,
        ))

        self.db.commit()
        self.db.refresh(course)
        self.db.refresh(lesson)
        return course, lesson, page_count, warning
