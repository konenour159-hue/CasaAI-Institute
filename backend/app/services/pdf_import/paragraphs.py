"""
Reconstruction des paragraphes (étape 3).

C'est l'étape qui corrige le défaut principal du moteur actuel. Celui-ci
sépare les paragraphes sur les lignes vides — or `extract_text()` n'en produit
pratiquement jamais : tout le texte d'une section finissait donc collé en un
seul bloc (jusqu'à 18 776 caractères d'un tenant sur un des ouvrages de
référence).

Avec la position enfin disponible, la frontière se lit directement dans
l'écart vertical entre deux lignes. Mesuré sur les trois ouvrages : l'interligne
courant est remarquablement stable (1,30 à 1,40 fois la taille de police, avec
des quartiles quasi confondus), tandis qu'une rupture de paragraphe apparaît
comme un saut franc (2,0 à 4,2 fois). Le seuil est donc exprimé relativement à
l'interligne médian du document lui-même, jamais en points absolus : les
documents n'ont ni la même taille de police ni le même interligne.
"""
from __future__ import annotations

import statistics

from app.services.pdf_import.models import Line, Page, Paragraph
from app.services.pdf_import.normalizer import join_lines
from app.services.pdf_import.patterns import looks_like_list_item

# Multiple de l'interligne médian au-delà duquel on considère qu'il y a
# rupture. Les mesures montrent un interligne courant très resserré autour de
# la médiane et des ruptures à 2,0x et au-delà : 1,5 sépare les deux sans
# ambiguïté, tout en absorbant les micro-variations d'arrondi.
_PARAGRAPH_GAP_FACTOR = 1.5

# Écart relatif de taille de police au-delà duquel deux lignes ne peuvent pas
# appartenir au même paragraphe (un titre et le corps qui le suit).
_FONT_CHANGE_TOLERANCE = 0.20

# Retrait de première ligne : une ligne qui commence nettement à droite de la
# marge du paragraphe en cours ouvre un nouveau paragraphe. Exprimé en
# fraction de la taille de police.
_INDENT_FACTOR = 0.8


def median_leading(pages: list[Page]) -> float:
    """Interligne médian du document, en points.

    Calculé sur les seules lignes consécutives d'une même page, et en écartant
    les écarts aberrants (changement de colonne, saut de bloc) qui fausseraient
    la médiane.
    """
    gaps: list[float] = []
    for page in pages:
        for current, following in zip(page.lines, page.lines[1:]):
            gap = current.y - following.y
            reference = max(current.font_size, 1.0)
            if 0 < gap < reference * 6:
                gaps.append(gap)
    return statistics.median(gaps) if gaps else 0.0


def _starts_new_paragraph(previous: Line, current: Line, *, leading: float, paragraph_left: float) -> bool:
    """Décide si `current` ouvre un nouveau paragraphe.

    Plusieurs signaux, jamais un seul (règle 6 du cahier) — et chacun
    correspond à une réalité typographique observable.
    """
    # Changement de page : jamais une rupture en soi. Un paragraphe qui se
    # poursuit d'une page à l'autre doit rester entier — c'est un acquis du
    # moteur actuel qu'il ne faut pas perdre. Les coordonnées y de deux pages
    # différentes ne sont de toute façon pas comparables.
    if current.page != previous.page:
        return False

    reference = max(previous.font_size, current.font_size, 1.0)

    # Une police nettement différente marque un changement de nature
    # (titre, légende, code) et donc un autre élément.
    if abs(current.font_size - previous.font_size) > reference * _FONT_CHANGE_TOLERANCE:
        return True

    # Un item de liste est toujours une unité en soi (§18) : sans cette
    # règle, une énumération se retrouve fondue dans le paragraphe qui
    # l'introduit (« Les langages les plus utilisés sont : - Python - Java »)
    # et la liste devient indétectable pour l'étape suivante.
    if looks_like_list_item(current.text):
        return True

    # Passage de prose à code, ou l'inverse.
    if (current.mono_ratio > 0.6) != (previous.mono_ratio > 0.6):
        return True

    # Passage d'une ligne entièrement en gras à de la prose ordinaire : c'est
    # un sous-titre, pas la même unité de texte. Ce signal complète celui de
    # la taille, qui peut être trop ténu pour trancher — cas relevé sur un
    # ouvrage réel où un sous-titre à 12 pt précède un corps à 9,7 pt, soit
    # 19 % d'écart, juste sous le seuil. Le seuil de 0,6 laisse passer les
    # amorces en gras (« Note : … ») qui font bien partie du paragraphe.
    if (current.bold_ratio > 0.6) != (previous.bold_ratio > 0.6):
        return True

    # L'interligne attendu dépend de la taille des lignes concernées, pas
    # seulement de la médiane du document : un titre en gros corps a un
    # interligne proportionnellement plus grand. Comparé à la seule médiane
    # (calculée sur le corps de texte), un titre de 30 pt sur trois lignes
    # était systématiquement éclaté en trois paragraphes — constaté sur un
    # ouvrage réel, dont le titre de chapitre ressortait en morceaux
    # (« Implementing » / « a GPT model from » / « scratch to generate text »).
    expected = max(leading, reference * 1.15)
    gap = previous.y - current.y
    if expected > 0 and gap > expected * _PARAGRAPH_GAP_FACTOR:
        return True

    # Retrait de première ligne, pour les documents qui marquent leurs
    # paragraphes par l'indentation plutôt que par l'espacement.
    if current.x > paragraph_left + reference * _INDENT_FACTOR:
        return True

    return False


def group_paragraphs(pages: list[Page]) -> list[Paragraph]:
    """Toutes les lignes du document → paragraphes ordonnés.

    Le parcours est continu d'une page à l'autre, de sorte qu'un paragraphe
    coupé par un saut de page reste un seul paragraphe.
    """
    # Les lignes annotées comme en-tête, pied ou numéro de page par
    # `margins.analyze_margins` sont écartées du contenu. Si l'analyse n'a pas
    # été lancée, aucune ligne n'est annotée et rien n'est filtré.
    ordered = [line for page in pages for line in page.lines if not line.boilerplate]
    if not ordered:
        return []

    leading = median_leading(pages)
    paragraphs: list[Paragraph] = []
    current: list[Line] = [ordered[0]]
    paragraph_left = ordered[0].x

    for line in ordered[1:]:
        if _starts_new_paragraph(current[-1], line, leading=leading, paragraph_left=paragraph_left):
            paragraphs.append(_build_paragraph(current))
            current = [line]
            paragraph_left = line.x
        else:
            current.append(line)
            paragraph_left = min(paragraph_left, line.x)

    paragraphs.append(_build_paragraph(current))
    return [paragraph for paragraph in paragraphs if paragraph.text]


def _build_paragraph(lines: list[Line]) -> Paragraph:
    return Paragraph(
        text=join_lines([line.text for line in lines]),
        lines=list(lines),
    )
