"""
Segmentation en blocs et reconstruction de la hiérarchie — étape 6.

C'est ici que se joue le principe directeur du cahier : « un paragraphe source
n'est PAS automatiquement un bloc ». Plusieurs paragraphes consécutifs de même
nature forment un seul bloc, tandis qu'un changement de nature en ouvre un
nouveau.

La hiérarchie doit tenir sur des documents mal formés (§17) : titres non
numérotés, niveaux manquants, numérotation irrégulière.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import (
    attach_lines,
    body_font_size,
    build_tree,
    classify_all,
    detect_tables,
    extract_pages,
    flatten,
    group_paragraphs,
    merge_overline_headings,
    size_bands,
    segment,
    should_start_new_block,
)
from app.services.pdf_import.blocks import (
    CAPTION_BLOCK,
    CODE_BLOCK,
    FORMULA_BLOCK,
    LIST_BLOCK,
    TABLE_BLOCK,
    TEXT_BLOCK,
)
from app.services.pdf_import.classifier import (
    CAPTION,
    CODE,
    HEADING,
    LIST_ITEM,
    PARAGRAPH,
    Classification,
)
from app.services.pdf_import.hierarchy import numbering_depth
from tests.pdf_fixtures import ALL_FIXTURES, Line, build_pdf


def structure_of(pdf_bytes: bytes):
    pages = attach_lines(extract_pages(pdf_bytes))
    body = body_font_size(pages)
    tables = detect_tables(pages)
    paragraphs = group_paragraphs(pages)
    results = classify_all(paragraphs, body)
    paragraphs, results = merge_overline_headings(paragraphs, results)
    elements = segment(paragraphs, results, tables)
    return build_tree(elements)


def _c(kind: str) -> Classification:
    return Classification(kind, 0.9)


# --- Frontières de bloc, testables isolément (§20) ---------------------------

def test_un_titre_ouvre_toujours_un_bloc():
    assert should_start_new_block(_c(PARAGRAPH), _c(HEADING)) is True
    assert should_start_new_block(None, _c(HEADING)) is True


def test_deux_paragraphes_consecutifs_ne_se_separent_pas():
    """Le cœur du §19 : ne pas produire un bloc par paragraphe."""
    assert should_start_new_block(_c(PARAGRAPH), _c(PARAGRAPH)) is False


def test_changement_de_nature_ouvre_un_bloc():
    assert should_start_new_block(_c(PARAGRAPH), _c(CODE)) is True
    assert should_start_new_block(_c(CODE), _c(PARAGRAPH)) is True
    assert should_start_new_block(_c(PARAGRAPH), _c(LIST_ITEM)) is True
    assert should_start_new_block(_c(LIST_ITEM), _c(CAPTION)) is True


def test_items_de_liste_consecutifs_restent_groupes():
    assert should_start_new_block(_c(LIST_ITEM), _c(LIST_ITEM)) is False


def test_le_premier_element_ouvre_un_bloc():
    assert should_start_new_block(None, _c(PARAGRAPH)) is True


# --- Segmentation ------------------------------------------------------------

def test_plusieurs_paragraphes_forment_un_seul_bloc():
    """Trois paragraphes distincts sous un même titre : un seul bloc, mais
    dont les paragraphes restent distincts à l'intérieur."""
    # Interligne courant de 17 pt à l'intérieur d'un paragraphe, saut de 43 pt
    # entre deux paragraphes : c'est le rapport observé sur les documents
    # réels, et le seul qui distingue une fin de paragraphe d'un retour à la
    # ligne ordinaire.
    pdf = build_pdf([[
        Line("Les donnees", y=740, size=18, font="bold"),
        Line("Les donnees constituent la matiere premiere de tout", y=680, size=11),
        Line("systeme d'apprentissage automatique moderne, et leur", y=663, size=11),
        Line("qualite conditionne celle des modeles produits.", y=646, size=11),
        Line("Elles peuvent etre structurees ou non structurees,", y=606, size=11),
        Line("selon la maniere dont elles ont ete collectees et", y=589, size=11),
        Line("selon le systeme qui les a produites.", y=572, size=11),
        Line("Elles sont utilisees a chaque etape du processus,", y=532, size=11),
        Line("depuis la conception initiale du modele jusqu'a son", y=515, size=11),
        Line("evaluation finale en conditions reelles.", y=498, size=11),
    ]])
    roots = structure_of(pdf)
    section = roots[0]
    assert section.title == "Les donnees"
    assert len(section.blocks) == 1, "les trois paragraphes forment un seul bloc"
    assert section.blocks[0].kind == TEXT_BLOCK
    assert len(section.blocks[0].paragraphs) == 3, "mais restent trois paragraphes distincts"
    assert "\n\n" in section.blocks[0].text


def test_liste_forme_un_bloc_avec_ses_items():
    """§21 : une liste ne doit pas être aplatie en texte."""
    roots = structure_of(ALL_FIXTURES["lists"]())
    blocks = [b for s in flatten(roots) for b in s.blocks]
    lists = [b for b in blocks if b.kind == LIST_BLOCK]
    assert lists
    items = lists[0].items
    assert len(items) >= 3
    assert any("Python" in item for item in items)


def test_code_forme_son_propre_bloc():
    roots = structure_of(ALL_FIXTURES["code"]())
    blocks = [b for s in flatten(roots) for b in s.blocks]
    kinds = {b.kind for b in blocks}
    assert CODE_BLOCK in kinds
    assert TEXT_BLOCK in kinds
    code = next(b for b in blocks if b.kind == CODE_BLOCK)
    assert "import pandas" in code.text


def test_legende_forme_son_propre_bloc():
    pdf = build_pdf([[
        Line("Le schema ci-dessous resume le pipeline complet,", y=700, size=11),
        Line("de la collecte jusqu'a la mise a disposition.", y=683, size=11),
        Line("Figure 2 - Architecture du pipeline", y=650, size=8),
        Line("Le texte courant reprend apres la figure,", y=610, size=11),
        Line("sans rapport direct avec la legende.", y=593, size=11),
    ]])
    blocks = [b for s in flatten(structure_of(pdf)) for b in s.blocks]
    kinds = {b.kind for b in blocks}
    assert CAPTION_BLOCK in kinds
    assert TEXT_BLOCK in kinds
    caption = next(b for b in blocks if b.kind == CAPTION_BLOCK)
    assert "Figure 2" in caption.text


# --- Profondeur de numérotation ----------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("1. Introduction", 1),
    ("1.2 Definition", 2),
    ("1.2.3 Exemple", 3),
    ("Introduction", 0),
    ("Chapitre 4", 0),
])
def test_profondeur_de_numerotation(text, expected):
    assert numbering_depth(text) == expected


# --- Hiérarchie --------------------------------------------------------------

def test_hierarchie_numerotee_reconstruite():
    roots = structure_of(ALL_FIXTURES["nested_headings"]())
    flat = flatten(roots)
    by_title = {s.title: s.level for s in flat}

    assert by_title["1. Donnees"] == 1
    assert by_title["1.1 Donnees structurees"] == 2
    assert by_title["1.1.1 Bases relationnelles"] == 3
    assert by_title["1.2 Donnees non structurees"] == 2
    assert by_title["2. Intelligence artificielle"] == 1


def test_parents_et_enfants_coherents():
    roots = structure_of(ALL_FIXTURES["nested_headings"]())
    donnees = roots[0]
    assert donnees.title == "1. Donnees"
    assert donnees.parent_id is None
    enfants = [child.title for child in donnees.children]
    assert "1.1 Donnees structurees" in enfants
    assert "1.2 Donnees non structurees" in enfants

    structurees = next(c for c in donnees.children if c.title.startswith("1.1 "))
    assert structurees.parent_id == donnees.id
    assert [c.title for c in structurees.children] == ["1.1.1 Bases relationnelles"]


def test_hierarchie_sans_numerotation_deduite_de_la_taille():
    """§17 : doit fonctionner sans numérotation. Le rang de taille de police
    suffit alors à ordonner les niveaux."""
    pdf = build_pdf([[
        Line("Titre principal", y=720, size=20, font="bold"),
        Line("Corps du premier niveau de lecture ici.", y=690, size=11),
        Line("Sous-titre", y=650, size=14, font="bold"),
        Line("Corps du second niveau de lecture ici.", y=620, size=11),
    ]])
    flat = flatten(structure_of(pdf))
    by_title = {s.title: s.level for s in flat}
    assert by_title["Titre principal"] == 1
    assert by_title["Sous-titre"] == 2


def test_niveau_manquant_ne_casse_pas_l_arbre():
    """§17 : un document qui saute un niveau (H1 puis H3) ne doit pas produire
    un arbre suspendu — le niveau est ramené à la profondeur atteignable."""
    pdf = build_pdf([[
        Line("1. Premier niveau", y=720, size=20, font="bold"),
        Line("Corps de texte du premier niveau.", y=690, size=11),
        Line("1.1.1 Niveau profond sans intermediaire", y=650, size=13, font="bold"),
        Line("Corps de texte du niveau profond.", y=620, size=11),
    ]])
    roots = structure_of(pdf)
    assert len(roots) == 1
    enfant = roots[0].children[0]
    assert enfant.level == 2, "le niveau 3 est ramené à 2, faute de parent intermédiaire"
    assert enfant.parent_id == roots[0].id


def test_contenu_avant_le_premier_titre_conserve():
    """Aucun contenu ne doit être perdu (règle 6) : ce qui précède le premier
    titre est rattaché à une section d'accueil."""
    pdf = build_pdf([[
        Line("Un preambule sans titre au-dessus de tout.", y=720, size=11),
        Line("1. Premier titre", y=670, size=18, font="bold"),
        Line("Le corps de la premiere section.", y=640, size=11),
    ]])
    roots = structure_of(pdf)
    assert roots[0].title == "Introduction"
    assert "preambule" in roots[0].blocks[0].text
    assert roots[1].title == "1. Premier titre"


def test_niveau_plafonne_a_quatre():
    pdf = build_pdf([[
        Line("1.1.1.1.1 Titre tres profond", y=720, size=18, font="bold"),
        Line("Corps de texte associe a ce titre.", y=690, size=11),
    ]])
    flat = flatten(structure_of(pdf))
    assert all(s.level <= 4 for s in flat)


# --- Traçabilité (§26, §45) --------------------------------------------------

def test_sections_et_blocs_conservent_leurs_pages():
    pdf = build_pdf([
        [Line("1. Titre", y=720, size=18, font="bold"),
         Line("Debut du contenu sur la premiere page.", y=680, size=11)],
        [Line("suite du contenu sur la seconde page.", y=700, size=11)],
    ])
    section = structure_of(pdf)[0]
    assert section.page_start == 0
    assert section.page_end == 1
    block = section.blocks[0]
    assert block.page_start == 0
    assert block.page_end == 1
    # La chaîne complète jusqu'aux lignes du PDF reste disponible.
    assert block.paragraphs[0].lines


def test_confidence_du_bloc_est_celle_de_son_element_le_moins_sur():
    pdf = build_pdf([[
        Line("Titre de section", y=720, size=18, font="bold"),
        Line("Un paragraphe de contenu tout a fait ordinaire.", y=680, size=11),
    ]])
    section = structure_of(pdf)[0]
    assert 0.0 <= section.blocks[0].confidence <= 1.0


@pytest.mark.parametrize("name", sorted(ALL_FIXTURES))
def test_structure_robuste_sur_toutes_les_fixtures(name):
    roots = structure_of(ALL_FIXTURES[name]())
    for section in flatten(roots):
        assert section.title.strip()
        assert 1 <= section.level <= 4
        assert section.id
        for block in section.blocks:
            assert block.kind in (
                    TEXT_BLOCK, LIST_BLOCK, CODE_BLOCK, CAPTION_BLOCK,
                    TABLE_BLOCK, FORMULA_BLOCK,
                )
            assert block.paragraphs


# --- Paliers de taille et surtitres (§16-17) ---------------------------------

def test_les_tailles_proches_relevent_du_meme_palier():
    """Classer les tailles distinctes une à une donnait, sur un ouvrage à six
    tailles de titre, des rangs de 1 à 6 : tout ce qui passait sous la
    quatrième s'écrasait au niveau 4. Les tailles relevées sur cet ouvrage."""
    bands = size_bands([30.0, 15.0, 14.0, 12.0, 11.6, 8.7])
    assert bands[30.0] == 1
    assert bands[15.0] == bands[14.0] == 2
    assert bands[12.0] == bands[11.6] == 3
    assert bands[8.7] == 4


def test_un_palier_ne_derive_pas_de_proche_en_proche():
    """Chaque taille est comparée à celle qui ouvre le palier, non à sa
    voisine : sinon une suite de petits écarts réunirait 15 pt et 12 pt."""
    bands = size_bands([15.0, 14.3, 13.6, 13.0, 12.4])
    assert bands[15.0] == bands[14.3] == 1
    assert bands[13.6] > 1


def test_le_surtitre_est_reuni_a_son_titre():
    """« Unit 18 » en 12 pt au-dessus de « Using a MySQL Database » en 14 pt
    n'est pas le parent de ce titre : c'est la même tête de chapitre en deux
    lignes. Séparés, le plus petit devenait parent du plus grand et emportait
    tout le chapitre suivant dans la branche précédente."""
    pdf = build_pdf([[
        Line("Unit 18", x=72, y=720, size=12),
        Line("Using a MySQL Database", x=72, y=700, size=14, font="bold"),
        Line("Cette unite presente les commandes de base du langage SQL.", x=72, y=670, size=10),
        Line("Insertion", x=72, y=640, size=12, font="bold"),
        Line("La commande INSERT ajoute une ligne dans une table existante.", x=72, y=620, size=10),
    ]])
    roots = structure_of(pdf)
    assert [section.title for section in roots] == ["Unit 18 Using a MySQL Database"]
    assert [child.title for child in roots[0].children] == ["Insertion"]


def test_un_titre_suivi_d_un_titre_plus_petit_reste_un_parent():
    """Le cas symétrique, qui ne doit surtout pas être fusionné : un vrai
    titre parent est lui aussi court, mais son sous-titre est plus petit."""
    pdf = build_pdf([[
        Line("Chapitre 1", x=72, y=720, size=18, font="bold"),
        Line("Les donnees", x=72, y=690, size=13, font="bold"),
        Line("Une donnee est une observation enregistree sur un support.", x=72, y=665, size=10),
    ]])
    roots = structure_of(pdf)
    assert [section.title for section in roots] == ["Chapitre 1"]
    assert [child.title for child in roots[0].children] == ["Les donnees"]


def test_deux_titres_eloignes_ne_sont_pas_fusionnes():
    """Un titre isolé en bas de page et le suivant en haut du bloc d'après ne
    forment pas une tête de chapitre : l'écart vertical les sépare."""
    pdf = build_pdf([[
        Line("Annexe", x=72, y=720, size=12),
        Line("Tableaux de reference", x=72, y=400, size=16, font="bold"),
        Line("Les tableaux ci-dessous rassemblent les valeurs usuelles.", x=72, y=375, size=10),
    ]])
    roots = structure_of(pdf)
    assert [section.title for section in roots] == ["Annexe", "Tableaux de reference"]
