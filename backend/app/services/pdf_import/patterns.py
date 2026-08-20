"""
Motifs de forme partagés entre les étapes.

Regroupés ici parce que la segmentation en paragraphes et la classification
ont besoin des mêmes : un item de liste doit à la fois ouvrir un paragraphe
(§18 — une liste est une unité distincte) et être reconnu comme tel ensuite
(§21). Les dupliquer exposerait à ce que les deux étapes divergent.
"""
from __future__ import annotations

import re

# Puces usuelles.
BULLET_RE = re.compile(r"^\s*[-–—•·*▪◦‣]\s+\S")

# Énumération à un seul niveau : « 1. », « 2) », « a. ». Volontairement plus
# stricte qu'un titre numéroté hiérarchique (« 1.2 »), qui n'est jamais un
# item de liste.
ORDERED_RE = re.compile(r"^\s*(\d{1,3}|[a-zA-Z])[.)]\s+\S")


def looks_like_list_item(text: str) -> bool:
    """Vrai si la ligne s'ouvre par une puce ou une énumération.

    Sert à isoler l'item comme unité propre. Décider s'il s'agit réellement
    d'une liste ou d'un titre numéroté relève de la classification, qui
    dispose en plus des signaux typographiques.
    """
    stripped = text.strip()
    return bool(BULLET_RE.match(stripped) or ORDERED_RE.match(stripped))
