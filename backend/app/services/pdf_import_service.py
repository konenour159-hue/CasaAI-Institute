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
import logging
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.content import Course, Lesson
from app.models.enums import ContentStatus
from app.repositories.admin_content_repository import AdminContentRepository
from app.repositories.document_structure_repository import DocumentStructureRepository
from app.services.pdf_import.report import log_report
from app.schemas.admin import AdminCourseIn, AdminLessonIn, AdminLessonSectionIn
from app.services.admin_content_service import ValidationError


logger = logging.getLogger("casa.pdf_import")


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


# Formats de numéro de page (§10 du cahier technique) : « 12 », « - 12 - »,
# « Page 4 », « p. 4 », « 4 / 20 », « 4 sur 20 ». Sert à autoriser la
# neutralisation des chiffres *uniquement* sur ces lignes-là — voir
# _detect_repeated_boilerplate pour la raison.
_PAGE_NUMBER_RE = re.compile(
    r"^\d{1,4}$"
    r"|^[-–—]\s*\d{1,4}\s*[-–—]$"
    r"|^p(?:age)?\.?\s*\d{1,4}\b"
    r"|^\d{1,4}\s*(?:/|sur|of|\|)\s*\d{1,4}$",
    re.IGNORECASE,
)

# Nombre de lignes considérées comme « marge » en haut et en bas de page.
# Un en-tête ou un pied de page y vit ; un titre de section, non.
_MARGIN_BAND = 2


def _looks_like_page_number(stripped: str) -> bool:
    return bool(_PAGE_NUMBER_RE.match(stripped))


def _norm_exact(line: str) -> str:
    """Normalisation conservatrice : espaces et casse seulement. Les chiffres
    sont préservés, ce qui distingue « Exercice 1 » de « Exercice 2 »."""
    return re.sub(r"\s+", " ", line.strip()).strip().lower()


def _norm_digits(line: str) -> str:
    """Normalisation agressive : les chiffres deviennent « # ». Réservée aux
    lignes qui ont déjà la forme d'un numéro de page."""
    return re.sub(r"\d+", "#", _norm_exact(line))


def _margin_positions(count: int) -> set[int]:
    """Positions (dans la liste des lignes non vides d'une page) considérées
    comme marge haute ou basse. La bande est réduite à 1 sur les pages très
    courtes, où une bande de 2 en haut *et* en bas couvrirait la page
    entière et exposerait tout le contenu au filtre."""
    if count <= 0:
        return set()
    band = _MARGIN_BAND if count > 4 else 1
    return set(range(min(band, count))) | set(range(max(0, count - band), count))


class _Boilerplate:
    """Décision multi-critères de suppression d'une ligne (règle 6 du cahier :
    « ne jamais supprimer un élément uniquement sur la base d'une règle
    unique »). Trois signaux sont combinés : la position dans la page, la
    répétition d'une page à l'autre, et la forme de la ligne.

    Historique de ce choix : la version précédente neutralisait les chiffres
    de *toutes* les lignes avant de compter les répétitions. Des titres
    légitimes ne différant que par leur numéro (« Exercice 1 », « Exercice
    2 »…) devenaient alors identiques, franchissaient le seuil, et étaient
    supprimés avec tout leur contenu — un document entier pouvait disparaître
    sans le moindre avertissement (cf. tests/test_pdf_import_current.py).

    La neutralisation des chiffres est donc désormais réservée aux lignes
    ayant déjà la forme d'un numéro de page, et toute suppression exige en
    plus que la ligne se trouve dans une marge.

    Contrepartie assumée : un en-tête dont seul un numéro varie au milieu
    d'un texte plus long (« Cours Big Data — page 4 ») n'est plus filtré. Le
    rattraper demanderait la position réelle et la taille de police, non
    disponibles à cette étape ; c'est prévu à l'étape « en-têtes/pieds » de
    la restructuration, avec ces signaux en appui.
    """

    def __init__(self, exact: set[str], numeric: set[str]):
        self.exact = exact
        self.numeric = numeric

    def matches(self, line: str, *, in_margin: bool) -> bool:
        if not in_margin:
            return False
        if _norm_exact(line) in self.exact:
            return True
        return _looks_like_page_number(line) and _norm_digits(line) in self.numeric


def _page_lines(page_text: str) -> list[str]:
    return [raw.strip() for raw in page_text.rstrip().split("\n")]


def _detect_repeated_boilerplate(
    pages: list[str], *, min_page_fraction: float = 0.25, min_occurrences: int = 3
) -> _Boilerplate:
    """En-têtes/pieds de page répétés — ex: le titre du document réimprimé en
    haut de chaque page. Sans ce filtre, une ligne de ce type est détectée
    comme un nouveau titre à *chaque* occurrence et fragmente le document en
    dizaines de sections vides (vérifié empiriquement : jusqu'à 30% des
    sections d'un import réel).

    Seules les lignes situées dans une marge sont comptabilisées : une ligne
    du corps de page n'est jamais candidate, quelle que soit sa répétition.
    """
    exact_counts: Counter[str] = Counter()
    numeric_counts: Counter[str] = Counter()

    for page_text in pages:
        non_empty = [line for line in _page_lines(page_text) if line]
        margins = _margin_positions(len(non_empty))
        seen_exact: set[str] = set()
        seen_numeric: set[str] = set()

        for position, line in enumerate(non_empty):
            if position not in margins or len(line) > 120:
                continue
            exact = _norm_exact(line)
            if exact and exact not in seen_exact:
                exact_counts[exact] += 1
                seen_exact.add(exact)
            if _looks_like_page_number(line):
                numeric = _norm_digits(line)
                if numeric and numeric not in seen_numeric:
                    numeric_counts[numeric] += 1
                    seen_numeric.add(numeric)

    threshold = max(min_occurrences, int(len(pages) * min_page_fraction))
    return _Boilerplate(
        exact={norm for norm, c in exact_counts.items() if c >= threshold},
        numeric={norm for norm, c in numeric_counts.items() if c >= threshold},
    )


# Item de liste ordonnée à un seul niveau : « 1. », « 2) ». Volontairement
# plus strict que _NUMBERED_HEADING_RE (pas de « 1.2 »), car un titre
# hiérarchique numéroté n'est jamais un item de liste.
_ORDERED_LIST_ITEM_RE = re.compile(r"^(\d{1,3})[.)]\s+\S")


def _ordered_list_number(line: str) -> int | None:
    match = _ORDERED_LIST_ITEM_RE.match(line)
    return int(match.group(1)) if match else None


def _detect_ordered_list_lines(lines: list[str]) -> set[int]:
    """Indices des lignes appartenant à une liste numérotée.

    « 1. Collecter les données » satisfait la regex de titre numéroté
    exactement comme « 1. Introduction » : sans distinction, chaque item
    devenait une section sans corps, et les sections vides étant écartées en
    fin de traitement, le contenu de la liste disparaissait purement et
    simplement (cf. tests/test_pdf_import_current.py).

    Le discriminant retenu est la *contiguïté* : des items de liste se
    suivent immédiatement avec une numérotation qui s'incrémente, alors que
    deux titres de section sont séparés par du corps de texte. Deux items
    consécutifs suffisent à trancher.
    """
    numbered = [(index, line) for index, line in enumerate(lines) if line]
    list_indices: set[int] = set()

    cursor = 0
    while cursor < len(numbered):
        start_number = _ordered_list_number(numbered[cursor][1])
        if start_number is None:
            cursor += 1
            continue

        run = [numbered[cursor][0]]
        expected = start_number + 1
        lookahead = cursor + 1
        while lookahead < len(numbered) and _ordered_list_number(numbered[lookahead][1]) == expected:
            run.append(numbered[lookahead][0])
            expected += 1
            lookahead += 1

        if len(run) >= 2:
            list_indices.update(run)
            cursor = lookahead
        else:
            cursor += 1

    return list_indices


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
        page_lines = _page_lines(page_text)

        # Positions de marge, exprimées en indices de ligne brute pour être
        # comparables à l'indice de boucle ci-dessous.
        non_empty_indices = [i for i, line in enumerate(page_lines) if line]
        margin_indices = {
            non_empty_indices[position] for position in _margin_positions(len(non_empty_indices))
        }
        list_indices = _detect_ordered_list_lines(page_lines)

        # « Première ligne de la page » au sens de la première ligne
        # réellement visible, une fois l'en-tête retiré — et non l'indice 0
        # brut. Sur un document doté d'un en-tête, l'indice 0 est justement
        # l'en-tête supprimé : le vrai premier titre de la page perdait alors
        # ce signal et n'était plus détecté (constaté en corrigeant la
        # suppression abusive d'en-têtes).
        seen_visible_line = False

        for i, line in enumerate(page_lines):
            if not line:
                flush_paragraph()
                prev_line_blank = True
                continue

            if boilerplate.matches(line, in_margin=(i in margin_indices)):
                # En-tête/pied de page répété : complètement ignoré, ni titre
                # ni contenu — ne modifie pas prev_line_blank (une ligne
                # invisible n'isole pas visuellement ce qui suit).
                continue

            is_first_visible = not seen_visible_line
            seen_visible_line = True

            # Un item de liste numérotée reste du contenu, jamais un titre.
            if i not in list_indices and _is_probable_heading(
                line, is_first_line_of_page=is_first_visible, prev_line_blank=prev_line_blank
            ):
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


def _build_document_structure(file_bytes: bytes):
    """Reconstruit l'arbre documentaire avec le nouveau moteur.

    Exécuté **en plus** du découpage historique, pas à sa place : les sections
    plates de la leçon restent produites à l'identique, donc l'affichage
    actuel ne change pas (§48, critère 18). L'arbre est stocké à côté, ce qui
    permet de comparer les deux sorties sur de vrais imports avant d'envisager
    la bascule.

    Toute erreur est absorbée : le nouveau moteur ne doit en aucun cas faire
    échouer un import qui réussissait auparavant.
    """
    from app.services.pdf_import import (
        analyze_margins,
        attach_lines,
        body_font_size,
        build_report,
        build_tree,
        classify_all,
        detect_tables,
        extract_pages,
        group_paragraphs,
        segment,
    )

    pages = attach_lines(extract_pages(file_bytes))
    body_size = body_font_size(pages)
    margins = analyze_margins(pages, body_size)
    # Les tableaux se lisent sur la géométrie des lignes, donc avant le
    # regroupement en paragraphes : c'est leur annotation qui empêche ensuite
    # de recoller les cellules entre elles.
    tables = detect_tables(pages)
    paragraphs = group_paragraphs(pages)
    classifications = classify_all(paragraphs, body_size)
    elements = segment(paragraphs, classifications, tables)
    roots = build_tree(elements)
    report = build_report(
        pages=pages, paragraphs=paragraphs, classifications=classifications,
        elements=elements, roots=roots, margins=margins,
    )
    return roots, report


def preview_pdf(*, file_bytes: bytes, filename: str) -> tuple[str, int, dict, list]:
    """Analyse un PDF **sans rien enregistrer** (§29).

    Rejoue exactement la chaîne de l'import : c'est la condition pour que la
    prévisualisation dise la vérité. Une analyse approchée, plus rapide mais
    différente, ne servirait à rien — l'utilisateur valide ce qu'il a vu.

    Renvoie le titre déduit, le nombre de pages, le rapport de qualité et
    l'arbre des sections.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
    except Exception as e:
        raise PdfExtractionError(f"Fichier PDF illisible : {e}") from e

    roots, report = _build_document_structure(file_bytes)
    return _title_from_filename(filename), page_count, report.to_dict(), roots


class PdfImportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminContentRepository(db)

    def import_pdf(
        self, *, file_bytes: bytes, filename: str, school_id: str
    ) -> tuple[Course, Lesson, int, str | None, object | None]:
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

        # Structure hiérarchique, écrite en parallèle des sections plates.
        # Un échec ici ne doit pas perdre l'import : le contenu est déjà
        # complet dans la leçon, l'arbre n'est qu'un enrichissement.
        report = None
        try:
            roots, report = _build_document_structure(file_bytes)
            DocumentStructureRepository(self.db).replace_for_lesson(lesson.id, roots)
            log_report(report, filename=filename)
        except Exception:
            logger.exception("Reconstruction de la structure documentaire impossible pour %s", filename)

        self.db.commit()
        self.db.refresh(course)
        self.db.refresh(lesson)
        return course, lesson, page_count, warning, report
