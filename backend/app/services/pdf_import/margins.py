"""
En-têtes, pieds de page et numéros de page (étape 4).

Le moteur actuel ne dispose que du texte : il repère les répétitions en
neutralisant les chiffres, ce qui l'a conduit à supprimer des documents
entiers dont les titres ne différaient que par un numéro. La correction de ce
bug a dû restreindre le filtre, au prix d'une couverture réduite — un en-tête
du type « 90 CHAPTER 3 Coding attention mechanisms » n'était plus détecté et
se retrouvait promu en titre de section.

La position rétablit cette couverture sur une base bien plus solide. Mesuré
sur les ouvrages de référence, le signal déterminant n'est pas le texte mais
la **bande de position** : un en-tête courant occupe systématiquement la même
distance au bord (33 pt, 35 pt, 5 pt selon les ouvrages) dans une police plus
petite que le corps, alors que son texte, lui, change à chaque page (titre de
chapitre, numéro). Chercher un texte répété était donc voué à échouer sur ces
documents ; chercher une bande occupée fonctionne.

Trois signaux concordants sont exigés avant toute mise à l'écart (règle 6) :
la bande, la récurrence de cette bande sur une part significative des pages,
et une caractéristique propre à la ligne (police plus petite que le corps,
forme de numéro de page, ou texte récurrent).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.services.pdf_import.models import Line, Page

# Zone de marge explorée, en fraction de la hauteur de page.
#
# Calibré sur les ouvrages de référence : les titres courants s'y trouvent à
# 33 et 35 pt du haut sur des pages de 666 et 648 pt, et le pied à 5 pt du
# bas — soit environ 5 %. Une bande à 15 % englobait les premières lignes du
# corps, qui, sur un document régulier, forment elles aussi une bande
# récurrente : elles se retrouvaient marquées comme en-tête et le contenu
# disparaissait. C'est très exactement le mode d'échec du bug corrigé
# précédemment, et la raison pour laquelle cette valeur doit rester serrée.
_MARGIN_FRACTION = 0.08

# Tolérance de regroupement de deux lignes dans une même bande, en points.
_BAND_TOLERANCE = 3.0

# Une bande doit être occupée sur au moins cette fraction des pages.
_BAND_PAGE_FRACTION = 0.5
_BAND_MIN_PAGES = 3

# Au-delà, une ligne est trop longue pour un en-tête ou un pied de page.
_MAX_BOILERPLATE_LENGTH = 120

# Formats de numéro de page (§10).
_PAGE_NUMBER_RE = re.compile(
    r"^\d{1,4}$"
    r"|^[-–—•·]\s*\d{1,4}\s*[-–—•·]?$"
    r"|^p(?:age)?\.?\s*\d{1,4}\b"
    r"|^\d{1,4}\s*(?:/|sur|of|\|)\s*\d{1,4}$",
    re.IGNORECASE,
)


def looks_like_page_number(text: str) -> bool:
    return bool(_PAGE_NUMBER_RE.match(text.strip()))


def _normalize(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.strip())).lower()


@dataclass
class MarginReport:
    """Trace des décisions prises, pour le rapport de qualité et le
    diagnostic (§34 : pouvoir expliquer pourquoi une ligne a été écartée)."""

    headers: int = 0
    footers: int = 0
    page_numbers: int = 0
    bands: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.headers + self.footers + self.page_numbers


def _margin_candidates(page: Page) -> list[tuple[Line, str, float]]:
    """Lignes situées dans une marge, avec leur bord et leur distance.

    Les lignes dont la position tombe hors de la page sont ignorées : sur des
    documents réels, une partie du contenu est rendue à des ordonnées
    négatives (contenu imbriqué que pypdf ne restitue pas intégralement). Une
    telle ligne n'est de toute façon pas un en-tête, et la traiter comme tel
    reviendrait à supprimer du contenu sur une mesure peu fiable.
    """
    limit = page.height * _MARGIN_FRACTION
    candidates: list[tuple[Line, str, float]] = []

    for line in page.lines:
        top = page.distance_from_top(line.y)
        bottom = page.distance_from_bottom(line.y)
        if not (0 <= top <= page.height and 0 <= bottom <= page.height):
            continue
        if len(line.text) > _MAX_BOILERPLATE_LENGTH:
            continue
        if top <= limit:
            candidates.append((line, "HEADER", top))
        elif bottom <= limit:
            candidates.append((line, "FOOTER", bottom))

    return candidates


def analyze_margins(pages: list[Page], body_size: float) -> MarginReport:
    """Marque en place les lignes d'en-tête, de pied et de numéro de page.

    Aucune ligne n'est supprimée ici : elles sont annotées, et c'est aux
    étapes suivantes de les écarter du contenu. Conserver la ligne permet de
    la faire figurer dans le rapport de qualité et de revenir sur la décision
    sans relire le PDF.
    """
    report = MarginReport()
    if not pages:
        return report

    # Regroupement des candidats par bord et bande de distance.
    buckets: dict[tuple[str, int], list[tuple[Line, int]]] = defaultdict(list)
    for page in pages:
        for line, edge, distance in _margin_candidates(page):
            band = int(round(distance / _BAND_TOLERANCE))
            buckets[(edge, band)].append((line, page.number))

    threshold = max(_BAND_MIN_PAGES, int(len(pages) * _BAND_PAGE_FRACTION))

    for (edge, band), entries in buckets.items():
        pages_touched = {page_number for _line, page_number in entries}
        if len(pages_touched) < threshold:
            continue

        lines = [line for line, _ in entries]
        repeated = {
            text for text, count in Counter(_normalize(line.text) for line in lines).items()
            if count >= threshold
        }

        marked_in_band = 0
        for line in lines:
            # Signal propre à la ligne, en plus de la bande récurrente.
            smaller_than_body = body_size > 0 and line.font_size < body_size * 0.95
            is_page_number = looks_like_page_number(line.text)
            is_repeated = _normalize(line.text) in repeated

            if not (smaller_than_body or is_page_number or is_repeated):
                continue

            if is_page_number:
                line.boilerplate = "PAGE_NUMBER"
                report.page_numbers += 1
            else:
                line.boilerplate = edge
                if edge == "HEADER":
                    report.headers += 1
                else:
                    report.footers += 1
            marked_in_band += 1

        if marked_in_band:
            report.bands.append(
                f"{edge} à {band * _BAND_TOLERANCE:.0f}pt du bord "
                f"sur {len(pages_touched)}/{len(pages)} pages ({marked_in_band} lignes)"
            )

    return report


def content_lines(pages: list[Page]) -> list[Line]:
    """Lignes de contenu, une fois les marges écartées."""
    return [line for page in pages for line in page.lines if not line.boilerplate]
