"""
Classification des éléments, par score et avec confidence (étapes 5, §12-14).

Le moteur actuel décide par une suite de conditions booléennes sur le texte
seul. Sur des documents réels, cela promeut en titres des formules
(« P(B|A) = P(A|B) × P(B) / P(A) »), des lignes de tableau, des légendes de
figures (« STAGE 1 », « 2) Attention ») et de la sortie SQL
(« 1 row in set (0.00 sec) »).

Ici, aucune décision ne repose sur un signal unique (règle 6) : les signaux
sont pondérés, le total est comparé à des seuils, et chaque décision conserve
la liste des raisons qui l'ont motivée (§34, explicabilité) ainsi qu'une
confidence (§14). Un élément ambigu n'est jamais forcé dans une catégorie :
il est classé avec une confidence basse et signalé au rapport de qualité.

Les pondérations partent de celles proposées par le cahier (§13) et ont été
ajustées d'après les mesures faites sur trois ouvrages réels : la taille de
police y est de loin le signal le plus discriminant (titres à 12,5 / 14 / 25 /
27,5 / 30 pt contre des corps à 9,7 / 10 / 15 pt), devant la graisse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.pdf_import.models import Paragraph
from app.services.pdf_import.patterns import BULLET_RE, ORDERED_RE

# --- Types d'éléments (§15) --------------------------------------------------
HEADING = "HEADING"
PARAGRAPH = "PARAGRAPH"
CODE = "CODE"
LIST_ITEM = "LIST_ITEM"
CAPTION = "CAPTION"
UNKNOWN = "UNKNOWN"

# Seuils de décision. Un score intermédiaire produit bien un titre, mais avec
# une confidence basse : le cahier demande de remonter ces cas plutôt que de
# trancher arbitrairement.
_HEADING_CONFIDENT = 70
_HEADING_POSSIBLE = 50

# Numérotation de titre : « 1. », « 1.2 », « I. », « Chapitre 3 ».
_NUMBERED_RE = re.compile(
    r"^(chapitre|chapter|partie|part|section|module|annexe|appendix|unit[ée]?|unit)\s+\d+\b"
    r"|^\d+(\.\d+)*[.)]?\s+\S"
    r"|^[IVXLCDM]{1,6}[.)]\s+\S",
    re.IGNORECASE,
)


# Légendes de figure ou de tableau (§25) : ne doivent pas devenir des titres.
_CAPTION_RE = re.compile(
    r"^(figure|fig\.?|tableau|table|listing|exemple|example|schema|schéma)\s*\d+", re.IGNORECASE
)

# Mots structurels usuels, français et anglais — les documents de référence
# mêlent les deux langues.
_STRUCTURAL_WORDS = {
    "introduction", "définition", "definition", "objectifs", "objectives",
    "principe", "principles", "fonctionnement", "applications", "exemple",
    "example", "avantages", "limites", "limitations", "conclusion",
    "synthèse", "summary", "méthodologie", "methodology", "architecture",
    "résultats", "results", "overview", "prérequis", "prerequisites",
    "références", "references", "annexe", "appendix",
}

_SENTENCE_END_RE = re.compile(r"[.!?…:;]$")
_MAX_HEADING_LENGTH = 120


@dataclass
class Classification:
    """Décision de classification, accompagnée de sa justification."""

    type: str
    confidence: float
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def is_ambiguous(self) -> bool:
        return self.confidence < 0.6


def _looks_title_case(text: str) -> bool:
    """Capitalisation de titre, convention courante en anglais (« Using a
    MySQL Database: Command Line »).

    Signal volontairement modeste : le français ne capitalise pas ses titres
    de cette façon, et les titres français des ouvrages de référence
    s'appuient de toute façon sur la taille et la graisse. Les mots de deux
    lettres ou moins sont ignorés, car articles et prépositions restent en
    minuscules même dans un titre.
    """
    words = [word for word in re.findall(r"[A-Za-zÀ-ÿ]+", text) if len(word) > 2]
    if not words:
        return False
    capitalized = sum(1 for word in words if word[0].isupper())
    return capitalized / len(words) >= 0.6


def _structural_word_hit(text: str) -> bool:
    first = re.split(r"[\s:,.]+", text.strip().lower(), maxsplit=1)
    return bool(first) and first[0] in _STRUCTURAL_WORDS


def _heading_score(paragraph: Paragraph, body_size: float) -> tuple[int, list[str]]:
    """Somme pondérée des indices en faveur d'un titre."""
    text = paragraph.text.strip()
    score = 0
    reasons: list[str] = []

    if body_size > 0:
        ratio = paragraph.font_size / body_size
        # Paliers recalés sur les ouvrages de référence : leurs sous-titres
        # réels (« Insertion », « Deletion », « Unit 18 ») se situent à 1,2x
        # le corps, et leurs titres de section à 1,4x. Des paliers à 1,25 et
        # 1,6 les laissaient tous sous le seuil de décision.
        if ratio >= 1.35:
            score += 45
            reasons.append(f"police {ratio:.1f}x le corps")
        elif ratio >= 1.15:
            score += 35
            reasons.append(f"police {ratio:.1f}x le corps")
        elif ratio >= 1.05:
            score += 20
            reasons.append(f"police {ratio:.1f}x le corps")
        elif ratio < 0.9:
            score -= 15
            reasons.append("police plus petite que le corps")

    if paragraph.bold_ratio > 0.6:
        score += 20
        reasons.append("texte en gras")

    if _looks_title_case(text):
        score += 10
        reasons.append("capitalisation de titre")

    if _NUMBERED_RE.match(text):
        score += 25
        reasons.append("numérotation de titre")

    if not _SENTENCE_END_RE.search(text):
        score += 10
        reasons.append("pas de ponctuation finale")

    if len(text) <= 60:
        score += 10
        reasons.append("ligne courte")
    elif len(text) > _MAX_HEADING_LENGTH:
        score -= 25
        reasons.append("trop long pour un titre")

    if _structural_word_hit(text):
        score += 10
        reasons.append("mot structurel")

    if len(paragraph.lines) > 3:
        score -= 15
        reasons.append("plus de trois lignes")

    return score, reasons


def classify(paragraph: Paragraph, body_size: float) -> Classification:
    """Détermine la nature d'un paragraphe.

    L'ordre des tests traduit la fiabilité des signaux : la chasse fixe et les
    formes de légende ou de puce sont quasi certaines, alors que la
    distinction titre / paragraphe demande une pondération.
    """
    text = paragraph.text.strip()
    if not text:
        return Classification(UNKNOWN, 0.0, reasons=["texte vide"])

    # Code : signal le plus fiable de tous, validé sur les ouvrages réels
    # (103 et 148 lignes détectées dans les deux livres techniques, aucune
    # dans l'ouvrage non technique).
    if paragraph.mono_ratio > 0.6:
        return Classification(
            CODE, min(0.95, 0.6 + paragraph.mono_ratio * 0.35),
            reasons=[f"police à chasse fixe ({paragraph.mono_ratio:.0%})"],
        )

    # Légende : « Figure 2 — Architecture ». Le cahier (§25) insiste sur le
    # fait qu'elle ne doit pas être prise pour un titre.
    if _CAPTION_RE.match(text):
        smaller = body_size > 0 and paragraph.font_size < body_size
        return Classification(
            CAPTION, 0.85 if smaller else 0.7,
            reasons=["forme de légende"] + (["police plus petite que le corps"] if smaller else []),
        )

    if BULLET_RE.match(text):
        return Classification(LIST_ITEM, 0.9, reasons=["puce en début de ligne"])

    score, reasons = _heading_score(paragraph, body_size)

    # Une énumération numérotée ressemble fortement à un titre numéroté. On ne
    # tranche que si les autres signaux typographiques ne plaident pas pour un
    # titre — c'est la même ambiguïté qui faisait disparaître les listes dans
    # le moteur actuel.
    if ORDERED_RE.match(text) and score < _HEADING_CONFIDENT:
        return Classification(
            LIST_ITEM, 0.7, score=score,
            reasons=["numérotation d'énumération", "signaux typographiques insuffisants pour un titre"],
        )

    if score >= _HEADING_CONFIDENT:
        confidence = min(0.98, 0.7 + (score - _HEADING_CONFIDENT) / 100)
        return Classification(HEADING, confidence, score=score, reasons=reasons)

    if score >= _HEADING_POSSIBLE:
        # Zone grise assumée : classé comme titre, mais signalé au rapport de
        # qualité plutôt que présenté comme certain (§14).
        return Classification(HEADING, 0.5, score=score, reasons=reasons + ["score intermédiaire"])

    return Classification(PARAGRAPH, min(0.95, 0.6 + (_HEADING_POSSIBLE - score) / 100), score=score,
                          reasons=reasons or ["aucun indice de titre"])


def classify_all(paragraphs: list[Paragraph], body_size: float) -> list[Classification]:
    return [classify(paragraph, body_size) for paragraph in paragraphs]
