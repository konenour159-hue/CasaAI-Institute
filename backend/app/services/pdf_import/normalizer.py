"""
Normalisation du texte (étape 3).

Deux responsabilités distinctes :

1. Nettoyer les caractères parasites d'un PDF (espaces insécables, caractères
   invisibles, ligatures) sans toucher à la typographie légitime.
2. Recoller les mots coupés en fin de ligne.

Ce qui n'est **pas** fait, volontairement : la normalisation Unicode NFKC.
Elle recollerait bien les ligatures, mais transformerait aussi « mc² » en
« mc2 » et détruirait donc le sens des formules — précisément un des types
d'éléments que le cahier demande de préserver (§23). Les ligatures sont donc
traitées explicitement, et la composition canonique reste en NFC.
"""
from __future__ import annotations

import re
import unicodedata

# Espaces exotiques → espace ordinaire. L'espace insécable est fréquent en
# typographie française (avant « : », « ; », « ? ») et casserait les
# comparaisons de texte s'il était conservé tel quel.
_SPACE_LIKE = dict.fromkeys(
    [0x00A0, 0x2007, 0x202F, 0x2009, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2008], " "
)

# Caractères sans rendu visible : ils faussent les longueurs et les
# comparaisons sans jamais rien apporter.
_INVISIBLE = dict.fromkeys([0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060], "")

# Ligatures typographiques, traitées explicitement plutôt que via NFKC.
_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}

_TRANSLATION = {**_SPACE_LIKE, **_INVISIBLE}

# Trait d'union conditionnel : inséré par le compositeur uniquement pour
# justifier le texte. Sa présence lève toute ambiguïté — contrairement au
# trait d'union ordinaire, il ne fait jamais partie du mot.
SOFT_HYPHEN = "­"

_HYPHEN_END_RE = re.compile(r"(\w{2,})[-‐‑]$")


def normalize_text(text: str) -> str:
    """Nettoie une chaîne extraite d'un PDF, en préservant sa ponctuation."""
    if not text:
        return ""
    cleaned = text.translate(_TRANSLATION)
    for ligature, replacement in _LIGATURES.items():
        cleaned = cleaned.replace(ligature, replacement)
    cleaned = unicodedata.normalize("NFC", cleaned)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def is_hyphenated_break(previous: str, following: str) -> bool:
    """Décide si deux lignes consécutives forment un mot coupé.

    Le cahier (§7) demande explicitement de ne pas appliquer une règle naïve
    à tous les tirets. Les signaux retenus :

    - un trait d'union conditionnel tranche à lui seul, sans ambiguïté ;
    - sinon, il faut un trait d'union final précédé d'au moins deux
      caractères de mot, et une suite commençant par une minuscule.

    La contrainte sur la minuscule écarte les composés propres coupés à leur
    trait d'union (« franco-/Allemand »), qui doivent le conserver.

    Limite assumée : un mot composé entièrement en minuscules et coupé
    exactement sur son trait d'union (« porte-/parole ») sera recollé à tort
    en « porteparole ». Trancher demanderait un dictionnaire ou un modèle de
    langue, exclus à cette étape (règle 1). Le cas est rare — la coupure doit
    tomber pile sur le trait d'union — et le compromis inverse (ne jamais
    recoller) dégraderait bien davantage le texte : 23 lignes concernées sur
    12 pages d'un seul des ouvrages de référence.
    """
    if not previous or not following:
        return False

    stripped_previous = previous.rstrip()
    if stripped_previous.endswith(SOFT_HYPHEN):
        return True

    if not _HYPHEN_END_RE.search(stripped_previous):
        return False

    first_char = following.lstrip()[:1]
    return bool(first_char) and first_char.islower()


def join_hyphenated(previous: str, following: str) -> str:
    """Recolle deux lignes formant un mot coupé, en retirant le trait
    d'union."""
    return previous.rstrip().rstrip(SOFT_HYPHEN).rstrip("-‐‑") + following.lstrip()


def join_lines(texts: list[str]) -> str:
    """Assemble les lignes d'un même paragraphe en un texte continu, en
    traitant les césures au passage."""
    result = ""
    for raw in texts:
        text = normalize_text(raw)
        if not text:
            continue
        if not result:
            result = text
        elif is_hyphenated_break(result, text):
            result = join_hyphenated(result, text)
        else:
            result = f"{result} {text}"
    return result
