"""
Extraction enrichie : PDF → fragments positionnés (étape 2).

Remplace la lecture `extract_text()` en texte pur par le visiteur de pypdf,
qui expose pour chaque fragment sa matrice de position, son dictionnaire de
police et sa taille. Vérifié sur trois documents réels (un ouvrage français,
deux ouvrages techniques anglais) : 100 % des fragments portent une taille et
un nom de police exploitables.

Deux pièges constatés sur ces mêmes documents, que ce module corrige :

1. La taille brute passée par pypdf est celle de l'opérateur `Tf`, sans
   l'échelle des matrices. Un des ouvrages déclare `Tf 1` partout et porte la
   taille réelle dans la matrice de texte : la valeur brute y vaut `1.0` pour
   la totalité du document. Après composition, on retrouve un corps à 10 pt et
   des titres à 12,5 pt.

2. Les coordonnées de la matrice de texte sont relatives à la matrice
   courante. Sur l'ouvrage français, `tm[4]` vaut 0 pour la quasi-totalité des
   fragments alors que le texte commence en réalité à x=80.

Sans ces deux corrections, taille et position sont inutilisables comme
signaux — ce qui invaliderait toute la suite de la chaîne.
"""
from __future__ import annotations

import io
import math

from pypdf import PdfReader

from app.services.pdf_import.models import Fragment, Page

# Marqueurs de graisse et de style dans un nom de police PostScript. Relevés
# sur les documents de référence : DINPro-Bold, Merriweather-LightItalic,
# FranklinGothic-DemiItal, HumanistMann521-BoldConden, DejaVuSansMono-Bold.
_BOLD_MARKERS = ("bold", "demi", "black", "heavy", "semib")
_ITALIC_MARKERS = ("italic", "ital", "oblique")
_MONO_MARKERS = ("mono", "courier", "consol")


def compose(tm: list[float], cm: list[float]) -> list[float]:
    """Produit matriciel `Tm × CTM` (affine 2×3).

    Donne la matrice de rendu réelle du texte, dont on tire la position
    absolue sur la page et le facteur d'échelle appliqué à la police.
    """
    return [
        tm[0] * cm[0] + tm[1] * cm[2],
        tm[0] * cm[1] + tm[1] * cm[3],
        tm[2] * cm[0] + tm[3] * cm[2],
        tm[2] * cm[1] + tm[3] * cm[3],
        tm[4] * cm[0] + tm[5] * cm[2] + cm[4],
        tm[4] * cm[1] + tm[5] * cm[3] + cm[5],
    ]


def _font_base_name(font_dict) -> str:
    if not font_dict:
        return ""
    base = font_dict.get("/BaseFont")
    if not base:
        return ""
    # Les polices embarquées sont préfixées d'un identifiant de sous-ensemble
    # (« ABCDEF+Helvetica ») sans intérêt pour nous.
    return str(base).lstrip("/").split("+")[-1]


def _style_flags(font_name: str) -> tuple[bool, bool, bool]:
    lowered = font_name.lower()
    bold = any(marker in lowered for marker in _BOLD_MARKERS)
    italic = any(marker in lowered for marker in _ITALIC_MARKERS)
    mono = any(marker in lowered for marker in _MONO_MARKERS)
    return bold, italic, mono


def _translated(tm: list[float], tx: float, ty: float) -> list[float]:
    """Matrice de texte après un déplacement relatif `tx ty Td`.

    `Td` déplace relativement à la matrice de ligne courante : additionner
    naïvement à `tm[4]`/`tm[5]` serait faux dès que le texte est mis à
    l'échelle ou tourné.
    """
    return [
        tm[0], tm[1], tm[2], tm[3],
        tx * tm[0] + ty * tm[2] + tm[4],
        tx * tm[1] + ty * tm[3] + tm[5],
    ]


def _recover_positions(calls: list[dict]) -> None:
    """Répare les positions dégénérées, en place.

    Filet de dernier recours, derrière le suivi des opérateurs de
    positionnement : il ne reste ici que les fragments dont la position n'a
    jamais été établie par un `Td`/`Tm` observable.

    On cherche la position valide la plus proche, en priorité vers l'avant :
    c'est là qu'elle se trouve dans le cas courant, où pypdf remonte le texte
    avant la matrice qui lui correspond.
    """
    def is_degenerate(call: dict) -> bool:
        return call["x"] == 0 and call["y"] == 0

    for index, call in enumerate(calls):
        if not is_degenerate(call):
            continue
        donor = next((c for c in calls[index + 1:] if not is_degenerate(c)), None)
        if donor is None:
            donor = next((c for c in reversed(calls[:index]) if not is_degenerate(c)), None)
        if donor is not None:
            call["x"] = donor["x"]
            call["y"] = donor["y"]


def extract_pages(file_bytes: bytes) -> list[Page]:
    """PDF → pages porteuses de fragments positionnés.

    Une seule passe de lecture par page (§43 : ne pas rescanner inutilement).
    Les appels du visiteur sont d'abord collectés tels quels — y compris ceux
    sans texte, qui portent parfois la seule position exploitable — puis
    filtrés une fois les positions réparées.

    Aucun regroupement en lignes ici : c'est la responsabilité de `layout`.
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[Page] = []

    for index, pdf_page in enumerate(reader.pages):
        box = pdf_page.mediabox
        page = Page(number=index, width=float(box.width), height=float(box.height))
        calls: list[dict] = []
        # Dernière position établie par un opérateur de positionnement. Voir
        # `operand` ci-dessous.
        pending: list[list[float] | None] = [None]

        def operand(operator, operands, cm, tm, _pending=pending):
            """Suit les opérateurs qui fixent la matrice de texte.

            pypdf remonte le texte *avant* la matrice qui lui correspond quand
            le fragment commence par une espace : le visiteur de texte reçoit
            alors une matrice à zéro, et la vraie position n'arrive qu'à
            l'appel suivant. Le dernier fragment d'une page n'a pas d'appel
            suivant — sa position était donc irrécupérable, et il héritait de
            celle de son voisin, qui peut appartenir à une autre colonne.

            Le visiteur d'opérandes, lui, voit passer le `Td` correspondant
            *avant* l'appel de texte : il suffit de le retenir.
            """
            name = operator.decode("latin-1") if isinstance(operator, bytes) else str(operator)
            if name in ("Td", "TD") and len(operands) >= 2:
                matrix = _translated(list(tm), float(operands[0]), float(operands[1]))
            elif name == "Tm" and len(operands) >= 6:
                matrix = [float(value) for value in operands[:6]]
            else:
                return
            _pending[0] = compose(matrix, list(cm))

        def visitor(text, cm, tm, font_dict, font_size, _calls=calls, _pending=pending):
            matrix = compose(list(tm), list(cm))
            if matrix[4] == 0 and matrix[5] == 0 and _pending[0] is not None:
                # Matrice dégénérée : la position — et l'échelle avec elle —
                # sont celles que le dernier opérateur a établies.
                matrix = _pending[0]
            # Échelle verticale effective : norme de la seconde ligne de la
            # matrice composée.
            scale = math.hypot(matrix[2], matrix[3])
            name = _font_base_name(font_dict)
            _calls.append({
                "text": text or "",
                "x": matrix[4],
                "y": matrix[5],
                "font_size": float(font_size or 0) * scale,
                "font_name": name,
            })

        pdf_page.extract_text(visitor_text=visitor, visitor_operand_before=operand)
        _recover_positions(calls)

        for call in calls:
            if not call["text"].strip():
                continue
            bold, italic, mono = _style_flags(call["font_name"])
            page.fragments.append(Fragment(
                text=call["text"],
                page=page.number,
                x=call["x"],
                y=call["y"],
                font_size=call["font_size"],
                font_name=call["font_name"],
                bold=bold,
                italic=italic,
                mono=mono,
            ))

        pages.append(page)

    return pages
