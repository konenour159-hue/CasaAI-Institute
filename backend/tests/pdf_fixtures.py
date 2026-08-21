"""
Générateur de PDF de test, sans dépendance externe.

Pourquoi générer plutôt que committer des .pdf binaires : les fixtures
restent lisibles et diffables en revue, et surtout chaque fixture contrôle
*exactement* la position, la taille et la police de chaque ligne — ce qui est
indispensable pour tester une logique basée sur la mise en page (le moteur
cible lit x/y/taille/police via le visiteur pypdf).

Limite assumée : ces PDF sont propres et bien formés. Ils prouvent le
comportement sur des cas maîtrisés, pas la robustesse sur des PDF réels
(polices exotiques, texte fragmenté par crénage, générateurs capricieux).
Des documents réels de la plateforme restent nécessaires pour valider le
moteur — cf. rapport d'audit Phase 0.

Écrit un PDF 1.4 minimal : catalogue, pages, une police par variante, et un
flux de contenu en texte non compressé (`BT /F1 11 Tf x y Td (…) Tj ET`).
"""
from __future__ import annotations

# Polices déclarées dans chaque page ; WinAnsiEncoding pour que les accents
# français (é, à, ç…) soient restitués correctement par pypdf.
FONTS = {
    "regular": ("F1", "/Helvetica"),
    "bold": ("F2", "/Helvetica-Bold"),
    "mono": ("F3", "/Courier"),
}

PAGE_WIDTH = 612
PAGE_HEIGHT = 792


def _escape(text: str) -> bytes:
    """Échappe les caractères réservés d'une chaîne littérale PDF, puis encode
    en latin-1 (WinAnsiEncoding). Les caractères hors latin-1 sont remplacés
    plutôt que de faire échouer la génération d'une fixture."""
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return escaped.encode("latin-1", errors="replace")


class Line:
    """Une ligne de texte positionnée sur une page.

    `y` suit la convention PDF : origine en bas de page, donc un y élevé est
    en haut. Les fixtures ci-dessous partent de 720 et descendent.

    `via_matrix=True` reproduit un procédé courant, observé sur un des
    documents réels de référence : la police est déclarée à `Tf 1` et la
    taille réelle est portée par la matrice de texte. La taille brute
    remontée par pypdf vaut alors 1 pour tout le document, et seule la
    composition des matrices permet de retrouver la vraie taille.
    """

    def __init__(
        self, text: str, *, x: int = 72, y: int, size: int = 11,
        font: str = "regular", via_matrix: bool = False,
    ):
        self.text = text
        self.x = x
        self.y = y
        self.size = size
        self.font = font
        self.via_matrix = via_matrix

    def to_stream(self) -> bytes:
        key = FONTS[self.font][0].encode()
        text = b"(" + _escape(self.text) + b") Tj\nET\n"
        if self.via_matrix:
            size = str(self.size).encode()
            return (
                b"BT\n/" + key + b" 1 Tf\n"
                + size + b" 0 0 " + size + b" "
                + str(self.x).encode() + b" " + str(self.y).encode() + b" Tm\n"
                + text
            )
        return (
            b"BT\n/" + key + b" " + str(self.size).encode() + b" Tf\n"
            + str(self.x).encode() + b" " + str(self.y).encode() + b" Td\n"
            + text
        )


def build_pdf(pages: list[list[Line]]) -> bytes:
    """Assemble un PDF complet à partir de pages de lignes positionnées."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # numéro d'objet (1-indexé)

    catalog_num = add(b"")   # réservé, réécrit à la fin (dépend de /Pages)
    pages_num = add(b"")     # réservé, dépend des pages

    font_nums: dict[str, int] = {}
    for name, (_key, base) in FONTS.items():
        font_nums[name] = add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont " + base.encode()
            + b" /Encoding /WinAnsiEncoding >>"
        )

    font_res = b" ".join(
        b"/" + FONTS[name][0].encode() + b" " + str(num).encode() + b" 0 R"
        for name, num in font_nums.items()
    )

    page_nums: list[int] = []
    for lines in pages:
        stream = b"".join(line.to_stream() for line in lines)
        content_num = add(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"
        )
        page_nums.append(add(
            b"<< /Type /Page /Parent " + str(pages_num).encode() + b" 0 R"
            + b" /MediaBox [0 0 " + str(PAGE_WIDTH).encode() + b" " + str(PAGE_HEIGHT).encode() + b"]"
            + b" /Resources << /Font << " + font_res + b" >> >>"
            + b" /Contents " + str(content_num).encode() + b" 0 R >>"
        ))

    kids = b" ".join(str(n).encode() + b" 0 R" for n in page_nums)
    objects[catalog_num - 1] = b"<< /Type /Catalog /Pages " + str(pages_num).encode() + b" 0 R >>"
    objects[pages_num - 1] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_nums)).encode() + b" >>"
    )

    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root "
        + str(catalog_num).encode() + b" 0 R >>\nstartxref\n"
        + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    return out


def _flow(items: list[tuple[str, str, int]], *, start_y: int = 720, x: int = 72) -> list[Line]:
    """Empile des lignes de haut en bas avec un interligne dépendant du rôle —
    un titre reçoit plus d'air au-dessus, comme dans un vrai document."""
    lines: list[Line] = []
    y = start_y
    for text, role, size in items:
        if lines and role in ("h1", "h2", "h3"):
            y -= 14  # respiration avant un titre
        font = "regular"
        if role in ("h1", "h2", "h3"):
            font = "bold"
        elif role == "code":
            font = "mono"
        lines.append(Line(text, x=x, y=y, size=size, font=font))
        y -= size + 6
    return lines


# --- Fixtures (§30 du cahier technique) -------------------------------------

def simple_course() -> bytes:
    """TEST 1/2 : un titre, puis plusieurs paragraphes consécutifs."""
    return build_pdf([_flow([
        ("Intelligence artificielle", "h1", 18),
        ("L'intelligence artificielle est un domaine de l'informatique.", "p", 11),
        ("Elle permet de resoudre des problemes complexes.", "p", 11),
        ("Elle est utilisee dans de nombreux secteurs.", "p", 11),
    ])])


def numbered_course() -> bytes:
    """TEST 4 : titres numérotés, signal le plus fiable."""
    return build_pdf([_flow([
        ("1. Intelligence artificielle", "h1", 16),
        ("L'intelligence artificielle est un domaine vaste.", "p", 11),
        ("2. Machine Learning", "h1", 16),
        ("Le Machine Learning constitue une sous-discipline.", "p", 11),
    ])])


def nested_headings() -> bytes:
    """TEST 5 : hiérarchie H1/H2/H3 à reconstruire."""
    return build_pdf([_flow([
        ("1. Donnees", "h1", 18),
        ("Les donnees constituent la matiere premiere.", "p", 11),
        ("1.1 Donnees structurees", "h2", 14),
        ("Elles suivent un schema predefini.", "p", 11),
        ("1.1.1 Bases relationnelles", "h3", 12),
        ("Le modele relationnel organise les donnees en tables.", "p", 11),
        ("1.2 Donnees non structurees", "h2", 14),
        ("Elles n'ont pas de schema fixe.", "p", 11),
        ("2. Intelligence artificielle", "h1", 18),
        ("L'IA exploite ces donnees.", "p", 11),
    ])])


def no_headings() -> bytes:
    """TEST 6 : document sans aucun titre — ne doit rien inventer (règle 8)."""
    return build_pdf([_flow([
        ("Les donnees constituent la matiere premiere de tout systeme.", "p", 11),
        ("Elles peuvent etre structurees ou non structurees.", "p", 11),
        ("Leur qualite conditionne la performance des modeles.", "p", 11),
    ])])


def headers_footers() -> bytes:
    """TEST 7/8/9 : en-tête répété, pied de page, numéro de page variable."""
    pages = []
    for page_no in range(1, 4):
        lines = [Line("Cours Big Data - Universite", x=72, y=750, size=9)]
        lines += _flow([
            (f"{page_no}. Chapitre {page_no}", "h1", 16),
            (f"Contenu pedagogique de la page {page_no}.", "p", 11),
            ("Suite du raisonnement sur cette meme page.", "p", 11),
        ], start_y=700)
        lines.append(Line("(c) 2024 Universite - Tous droits reserves", x=72, y=60, size=9))
        lines.append(Line(str(page_no), x=300, y=40, size=9))
        pages.append(lines)
    return build_pdf(pages)


def lists_document() -> bytes:
    """TEST 10 : listes à puces et numérotées, ne doivent pas être aplaties."""
    return build_pdf([_flow([
        ("Langages de programmation", "h1", 16),
        ("Les langages les plus utilises sont :", "p", 11),
        ("- Python", "li", 11),
        ("- Java", "li", 11),
        ("- C++", "li", 11),
        ("Les etapes a suivre sont les suivantes :", "p", 11),
        ("1. Collecter les donnees", "li", 11),
        ("2. Entrainer le modele", "li", 11),
        ("3. Evaluer les resultats", "li", 11),
    ])])


def tables_document() -> bytes:
    """TEST 11 : tableau aligné en colonnes (positions x distinctes)."""
    lines = _flow([
        ("Algorithmes", "h1", 16),
        ("Le tableau ci-dessous resume les usages.", "p", 11),
    ])
    y = 640
    for left, right in [("Algorithme", "Usage"), ("KNN", "Classification"), ("KMeans", "Clustering")]:
        lines.append(Line(left, x=72, y=y, size=11, font="bold" if left == "Algorithme" else "regular"))
        lines.append(Line(right, x=260, y=y, size=11, font="bold" if left == "Algorithme" else "regular"))
        y -= 20
    return build_pdf([lines])


def formulas_document() -> bytes:
    """TEST 12 : formule isolée, ne doit pas devenir une phrase ordinaire."""
    return build_pdf([_flow([
        ("Energie", "h1", 16),
        ("La relation entre masse et energie s'ecrit :", "p", 11),
        ("E = mc2", "formula", 12),
        ("Cette equation etablit une equivalence.", "p", 11),
    ])])


def code_document() -> bytes:
    """TEST 13 : bloc de code en police à chasse fixe."""
    return build_pdf([_flow([
        ("Manipulation de donnees", "h1", 16),
        ("On importe d'abord la bibliotheque :", "p", 11),
        ("import pandas as pd", "code", 10),
        ("df = pd.read_csv('data.csv')", "code", 10),
        ("Les donnees sont alors disponibles.", "p", 11),
    ])])


# Partagé par les deux fixtures à colonnes, pour que la seule différence
# entre elles soit le titre pleine largeur.
_TWO_COLUMN_ROWS = [
    ("La donnee est la matiere", "Le modele apprend ensuite"),
    ("premiere de tout systeme", "a partir de ces exemples"),
    ("d'apprentissage automatique.", "pour generaliser."),
    ("Sans jeu de donnees fiable,", "Cette capacite a traiter"),
    ("aucun modele ne peut etre", "des situations nouvelles"),
    ("entraine correctement, quelle", "constitue le coeur meme"),
    ("que soit la qualite de", "de la demarche, et son"),
    ("l'algorithme retenu ensuite.", "principal critere de succes."),
]


def two_columns() -> bytes:
    """TEST 14 : deux colonnes, flux de contenu **entrelacé** (gauche, droite,
    gauche, droite… à y égal).

    C'est le cas difficile réel : beaucoup de générateurs écrivent le contenu
    ligne visuelle par ligne visuelle et non colonne par colonne. Sans
    détection de colonnes, la lecture mélange alors les deux colonnes. Un
    flux déjà ordonné par colonne ne prouverait rien — l'ordre serait correct
    par accident.

    Les colonnes comptent volontairement plusieurs lignes bien remplies :
    c'est ce qui distingue une vraie mise en colonnes d'un tableau à deux
    colonnes, dont les cellules sont courtes et peu nombreuses (cf.
    `tables_document`, qui ne doit *pas* être pris pour deux colonnes).
    """
    lines: list[Line] = []
    y = 700
    for left, right in _TWO_COLUMN_ROWS:
        lines.append(Line(left, x=72, y=y, size=11))
        lines.append(Line(right, x=330, y=y, size=11))
        y -= 17
    return build_pdf([lines])


def two_columns_with_banner() -> bytes:
    """Deux colonnes surmontées d'un titre courant sur toute la largeur.

    Cas très répandu dans les documents académiques, et piège pour la
    détection : le titre traverse la gouttière et la ferait disparaître du
    profil. Il doit rester à sa place dans l'ordre de lecture, avant les deux
    colonnes.
    """
    lines: list[Line] = [Line("Apprentissage automatique supervise", x=72, y=730, size=16, font="bold")]
    y = 700
    for left, right in _TWO_COLUMN_ROWS:
        lines.append(Line(left, x=72, y=y, size=11))
        lines.append(Line(right, x=330, y=y, size=11))
        y -= 17
    return build_pdf([lines])


def repeated_numbered_headings() -> bytes:
    """Cas limite découvert en construisant ce filet de sécurité : des titres
    numérotés récurrents (« Exercice 1 », « Exercice 2 »…) que la
    normalisation `\\d+ → #` rend identiques, et que le filtre d'en-têtes
    répétés supprime alors comme du bruit. Voir test_pdf_import_current.py."""
    pages = []
    for n in range(1, 4):
        lines = [Line("Support de cours - Statistiques", x=72, y=750, size=9)]
        lines += _flow([
            (f"Exercice {n}", "h1", 16),
            (f"Enonce numero {n} a traiter en autonomie.", "p", 11),
        ], start_y=700)
        pages.append(lines)
    return build_pdf(pages)


def hyphenation() -> bytes:
    """TEST 15 : mot coupé en fin de ligne, à recoller — sans casser un vrai
    mot composé (« porte-parole ») présent volontairement juste après."""
    return build_pdf([_flow([
        ("Definitions", "h1", 16),
        ("L'intel-", "p", 11),
        ("ligence artificielle progresse vite.", "p", 11),
        ("Le porte-parole a confirme cette avancee.", "p", 11),
    ])])


def complex_course() -> bytes:
    """TEST 12 (cahier) : document multi-pages mêlant tous les cas."""
    page1 = [Line("Cours IA - Support", x=72, y=750, size=9)]
    page1 += _flow([
        ("1. Introduction", "h1", 18),
        ("Ce cours presente les fondements de l'intelligence artificielle.", "p", 11),
        ("Il s'adresse a un public deja familier des donnees.", "p", 11),
        ("1.1 Objectifs", "h2", 14),
        ("A l'issue de ce cours, vous saurez :", "p", 11),
        ("- Definir l'IA", "li", 11),
        ("- Distinguer les approches", "li", 11),
    ], start_y=700)
    page1.append(Line("1", x=300, y=40, size=9))

    page2 = [Line("Cours IA - Support", x=72, y=750, size=9)]
    page2 += _flow([
        ("2. Apprentissage automatique", "h1", 18),
        ("L'apprentissage automatique repose sur les donnees.", "p", 11),
        ("2.1 Apprentissage supervise", "h2", 14),
        ("Le modele apprend a partir d'exemples annotes.", "p", 11),
        ("from sklearn import svm", "code", 10),
    ], start_y=700)
    page2.append(Line("2", x=300, y=40, size=9))

    return build_pdf([page1, page2])


def scaled_text_matrix() -> bytes:
    """Taille de police portée par la matrice de texte (`Tf 1` + `Tm`).

    Reproduit le comportement d'un des ouvrages de référence, où la taille
    brute vaut 1 pour la totalité du document. Sans composition des matrices,
    tous les fragments paraissent de même taille et le signal « titre plus
    gros que le corps » disparaît complètement.
    """
    return build_pdf([[
        Line("Titre porte par la matrice", x=72, y=720, size=20, font="bold", via_matrix=True),
        Line("Corps de texte porte par la matrice.", x=72, y=690, size=10, via_matrix=True),
        Line("Seconde ligne de corps.", x=72, y=674, size=10, via_matrix=True),
    ]])


def multi_fragment_line() -> bytes:
    """Une même ligne visuelle éclatée en plusieurs fragments (changement de
    police en cours de ligne), à recoller en une seule ligne — mesuré entre
    1,1 et 2,3 fragments par ligne sur les documents réels."""
    return build_pdf([[
        Line("Le terme ", x=72, y=700, size=11),
        Line("important", x=125, y=700, size=11, font="bold"),
        Line(" est defini ici.", x=185, y=700, size=11),
        Line("Ligne suivante, distincte.", x=72, y=680, size=11),
    ]])


ALL_FIXTURES = {
    "simple_course": simple_course,
    "numbered_course": numbered_course,
    "nested_headings": nested_headings,
    "no_headings": no_headings,
    "headers_footers": headers_footers,
    "lists": lists_document,
    "tables": tables_document,
    "formulas": formulas_document,
    "code": code_document,
    "two_columns": two_columns,
    "two_columns_with_banner": two_columns_with_banner,
    "hyphenation": hyphenation,
    "complex_course": complex_course,
    "repeated_numbered_headings": repeated_numbered_headings,
    "scaled_text_matrix": scaled_text_matrix,
    "multi_fragment_line": multi_fragment_line,
}
