"""
Modèle intermédiaire du moteur d'import PDF (étape 2 de la restructuration).

Deux niveaux seulement à ce stade, volontairement :

    Fragment — un morceau de texte tel que pypdf le restitue, avec sa
               position réelle sur la page et sa police.
    Line     — des fragments regroupés par ligne visuelle.

Rien de sémantique ici : ni titre, ni paragraphe, ni bloc. La classification
viendra plus tard, et elle s'appuiera sur ces mesures plutôt que sur des
heuristiques de texte brut.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fragment:
    """Un fragment de texte positionné.

    `font_size` est la taille **effective**, après composition de la matrice
    de texte et de la matrice courante — pas la valeur brute de l'opérateur
    `Tf`. Sur des PDF réels, cette distinction est déterminante : un des
    documents de référence déclare `Tf 1` pour absolument tout son texte et
    porte la taille réelle dans la matrice. La valeur brute y est donc
    constante, donc inutilisable comme signal.
    """

    text: str
    page: int
    x: float
    y: float
    font_size: float
    font_name: str
    bold: bool
    italic: bool
    mono: bool


@dataclass
class Line:
    """Une ligne visuelle, reconstruite en regroupant les fragments partageant
    la même ordonnée."""

    text: str
    page: int
    x: float
    y: float
    font_size: float
    fragments: list[Fragment] = field(default_factory=list)

    @property
    def bold_ratio(self) -> float:
        """Part du texte en gras. Un ratio plutôt qu'un booléen : une ligne
        peut n'avoir que ses premiers mots en gras (« Note : … »), ce qui ne
        doit pas la faire passer pour un titre."""
        return self._ratio(lambda f: f.bold)

    @property
    def italic_ratio(self) -> float:
        return self._ratio(lambda f: f.italic)

    @property
    def mono_ratio(self) -> float:
        """Part du texte en police à chasse fixe — signal principal pour
        distinguer du code d'un paragraphe (vérifié sur les documents de
        référence : `CourierStd`, `DejaVuSansMono-Bold`)."""
        return self._ratio(lambda f: f.mono)

    def _ratio(self, predicate) -> float:
        total = sum(len(f.text.strip()) for f in self.fragments)
        if not total:
            return 0.0
        matching = sum(len(f.text.strip()) for f in self.fragments if predicate(f))
        return matching / total


@dataclass
class Paragraph:
    """Plusieurs lignes visuelles formant une unité de texte continue.

    Conserve les lignes d'origine plutôt que le seul texte assemblé : c'est ce
    qui permet de remonter à la page et à la position de chaque élément (§26
    traçabilité), et ce dont dépendra le futur découpage RAG (§45).
    """

    text: str
    lines: list[Line] = field(default_factory=list)

    @property
    def page_start(self) -> int:
        return min(line.page for line in self.lines) if self.lines else -1

    @property
    def page_end(self) -> int:
        return max(line.page for line in self.lines) if self.lines else -1

    @property
    def font_size(self) -> float:
        """Taille représentative, pondérée par la longueur de chaque ligne."""
        weighted: list[float] = []
        for line in self.lines:
            weighted.extend([line.font_size] * max(len(line.text), 1))
        return statistics.median(weighted) if weighted else 0.0

    @property
    def mono_ratio(self) -> float:
        total = sum(len(line.text) for line in self.lines)
        if not total:
            return 0.0
        return sum(len(line.text) * line.mono_ratio for line in self.lines) / total

    @property
    def bold_ratio(self) -> float:
        total = sum(len(line.text) for line in self.lines)
        if not total:
            return 0.0
        return sum(len(line.text) * line.bold_ratio for line in self.lines) / total


@dataclass
class Page:
    """Une page extraite, avec ses dimensions — nécessaires pour raisonner en
    distance aux marges plutôt qu'en coordonnées absolues (une même valeur y
    n'a pas le même sens sur A4 et sur un format poche)."""

    number: int
    width: float
    height: float
    fragments: list[Fragment] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)

    def distance_from_top(self, y: float) -> float:
        return self.height - y

    def distance_from_bottom(self, y: float) -> float:
        return y
