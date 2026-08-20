"""
Script de seed : recharge le contenu pédagogique du prototype
(`CASA_AI_Institute_V2.html` → `window.CASA_DATA`, exporté ici en
`data/casa_data.json`) dans la base PostgreSQL via les modèles SQLAlchemy.

Ne seed QUE le contenu de référence (écoles, compétences, parcours, cours,
leçons, labs, questions, ressources, glossaire, graphe de connaissances,
certifications, gouvernance). Ne crée aucun utilisateur ni aucune donnée de
progression — cela viendra avec l'authentification (étape suivante).

Idempotent : peut être relancé sans dupliquer les données (upsert par clé
primaire naturelle héritée du prototype, cf. `_get_or_create`).

Usage :
    export DATABASE_URL="postgresql+psycopg2://casa:casa@localhost:5432/casa_dev"
    python -m scripts.seed
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.catalog import School, Skill
from app.models.certification import Certification, CertificationRequirement
from app.models.content import (
    Course,
    Demo,
    Lesson,
    LessonDepthLevel,
    LessonObjective,
    LessonSection,
    Pathway,
    pathway_courses,
)
from app.models.enums import CertificationRequirementType, ContentStatus, LessonDepthKey
from app.models.knowledge import (
    KnowledgeNode,
    KnowledgeNodeApplication,
    knowledge_node_demos,
    knowledge_node_dependencies,
    knowledge_node_labs,
    knowledge_node_used_in_lessons,
)
from app.models.lab import Lab, lab_modes, lab_skills
from app.models.quiz import Question, QuestionBank, QuestionOption, Quiz, quiz_questions
from app.models.enums import QuizKind
from app.models.resource import (
    GlossaryTerm,
    GovernanceJurisdiction,
    GovernanceStandard,
    Resource,
    resource_courses,
    resource_tags,
)
from app.models.user import Goal, LearnerProfileType

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "casa_data.json"

DEPTH_KEY_MAP = {
    "essential": LessonDepthKey.ESSENTIAL,
    "technical": LessonDepthKey.TECHNICAL,
    "mathematics": LessonDepthKey.MATHEMATICS,
    "implementation": LessonDepthKey.IMPLEMENTATION,
    "architecture": LessonDepthKey.ARCHITECTURE,
    "governance": LessonDepthKey.GOVERNANCE,
}

DEPTH_LABELS_FR = {
    "essential": "Essentiel",
    "technical": "Technique",
    "mathematics": "Mathématiques",
    "implementation": "Implémentation",
    "architecture": "Architecture",
    "governance": "Gouvernance & risques",
}


def _get_or_create(db: Session, model, pk_value: Any, **fields):
    """Upsert simple par clé primaire : évite de dupliquer si le script est
    relancé. `pk_value` doit être la valeur de la colonne primaire du modèle."""
    pk_col = list(model.__table__.primary_key.columns)[0]
    instance = db.get(model, pk_value)
    if instance is None:
        instance = model(**{pk_col.name: pk_value}, **fields)
        db.add(instance)
    else:
        for k, v in fields.items():
            setattr(instance, k, v)
    return instance


def seed_schools(db: Session, data: dict) -> None:
    for s in data["schools"]:
        _get_or_create(
            db, School, s["id"],
            name=s["name"], short_name=s["short"], color=s["color"], description=s.get("description"),
        )
    db.flush()
    print(f"  schools: {len(data['schools'])}")


def seed_skills(db: Session, data: dict) -> None:
    for s in data["skills"]:
        _get_or_create(
            db, Skill, s["id"],
            school_id=s["schoolId"], name=s["name"], description=s.get("description"),
        )
    db.flush()
    print(f"  skills: {len(data['skills'])}")


def seed_profile_types_and_goals(db: Session, data: dict) -> None:
    for p in data["profiles"]:
        _get_or_create(db, LearnerProfileType, p["id"], name=p["name"], description=p.get("description"))
    for g in data["goals"]:
        _get_or_create(db, Goal, g["id"], label=g["label"])
    db.flush()
    print(f"  learner_profile_types: {len(data['profiles'])}, goals: {len(data['goals'])}")


def seed_demos(db: Session, data: dict) -> None:
    for d in data["demos"]:
        _get_or_create(
            db, Demo, d["id"],
            title=d["title"], description=d.get("description"),
            component_key=d["id"], status=ContentStatus.PUBLISHED,
        )
    db.flush()
    print(f"  demos: {len(data['demos'])}")


# Cours du prototype volontairement fusionnés en cours plus larges (cf.
# discussion de conception « condenser les cours ») — ne doivent plus jamais
# être recréés ni réassociés à un parcours par un reseed, sous peine de
# ressusciter la fragmentation d'origine à côté du cours fusionné. Voir le
# mapping complet dans l'historique de la migration ; les nouveaux id
# (agents-ia, donnees-architecture, gouvernance-ia, infrastructure-mlops,
# rag-complet, machine-learning, mathematiques-ia) ne viennent pas du
# prototype, ce script ne les touche donc jamais.
_MERGED_AWAY_COURSE_IDS = {
    "agent-engineering", "agents", "agents-panorama",
    "data", "data-architecture", "distributed-data",
    "global-governance", "governance", "iso42001",
    "llm-systems", "mlops", "systems-ai",
    "rag", "rag-engineering",
    "ml", "ml-advanced",
    "information-theory-ai", "math-ai",
}

# Leçons du prototype fusionnées à la main dans une autre leçon survivante du
# même sujet (doublon issu de la fusion de deux cours prototype qui
# couvraient la même matière — ex: agents-ia contenait à la fois "agent-loop"
# et "agent-loop-tools" sur la boucle agentique). Certaines pointent vers un
# course_id du prototype lui-même dans _MERGED_AWAY_COURSE_IDS (ex:
# "agent-engineering") : les recréer provoquerait une violation de clé
# étrangère puisque ce cours n'existe plus. Jamais recréées par ce script.
_MERGED_AWAY_LESSON_IDS = {
    "agent-loop-tools", "agent-memory-planning", "agent-evaluation-governance",
    "data-quality-lineage",
}


def seed_pathways_and_courses(db: Session, data: dict) -> None:
    for p in data["pathways"]:
        _get_or_create(
            db, Pathway, p["id"],
            title=p["title"], profile_label=p.get("profile"), level=p.get("level"),
            duration_label=p.get("duration"), color=p.get("color"), description=p.get("description"),
            status=ContentStatus.PUBLISHED,
        )
    created_courses = 0
    for c in data["courses"]:
        if c["id"] in _MERGED_AWAY_COURSE_IDS:
            continue
        if db.get(Course, c["id"]) is None:
            created_courses += 1
        _get_or_create(
            db, Course, c["id"],
            school_id=c["schoolId"], title=c["title"], level=c.get("level"),
            duration_min=c.get("duration"), color=c.get("color"), description=c.get("description"),
            status=ContentStatus.PUBLISHED,
        )
    db.flush()

    # pathway_courses : position = index dans pathway['courses']
    for p in data["pathways"]:
        for position, course_id in enumerate(p.get("courses", [])):
            if course_id in _MERGED_AWAY_COURSE_IDS:
                continue
            existing = db.execute(
                pathway_courses.select().where(
                    pathway_courses.c.pathway_id == p["id"],
                    pathway_courses.c.course_id == course_id,
                )
            ).first()
            if existing is None:
                db.execute(pathway_courses.insert().values(
                    pathway_id=p["id"], course_id=course_id, position=position
                ))
    db.flush()
    print(f"  pathways: {len(data['pathways'])}, courses: {created_courses} nouveaux créés "
          f"({len(_MERGED_AWAY_COURSE_IDS)} cours du prototype fusionnés ailleurs, jamais recréés)")


def seed_lessons(db: Session, data: dict) -> None:
    """Amorce les leçons depuis le prototype — UNE SEULE FOIS par leçon.

    Contrairement aux autres fonctions seed_*, une leçon déjà présente en
    base n'est PLUS jamais retouchée par ce script : ni son propre corps
    (title/summary/example), ni ses objectifs/sections/niveaux de
    profondeur. Nécessaire depuis qu'un cours peut être enrichi à la main
    (corps de section approfondi, exemples, schémas — cf. discussion de
    conception « enrichissement de contenu ») : sans cette garde, rejouer
    `python -m scripts.seed` pour une tout autre raison (ex: ajouter une
    bibliographie sur un autre cours) écrasait silencieusement cet
    enrichissement en réimportant le texte brut du prototype (vécu
    concrètement lors de l'enrichissement du cours "fundamentals").
    Seules les leçons pas encore en base sont créées."""
    # position d'une leçon = son index dans course['lessons'], pas dans data['lessons']
    lesson_position: dict[str, int] = {}
    for c in data["courses"]:
        for position, lesson_id in enumerate(c.get("lessons", [])):
            lesson_position[lesson_id] = position

    created = 0
    for l in data["lessons"]:
        if l["id"] in _MERGED_AWAY_LESSON_IDS:
            continue
        if db.get(Lesson, l["id"]) is not None:
            continue
        created += 1

        lesson = Lesson(
            id=l["id"], course_id=l["courseId"], skill_id=l.get("skillId"), demo_id=l.get("demoId"),
            title=l["title"], level=l.get("level"), duration_min=l.get("duration"),
            summary=l.get("summary"), example=l.get("example"),
            position=lesson_position.get(l["id"], 0),
            status=ContentStatus.PUBLISHED,
        )
        db.add(lesson)
        db.flush()  # nécessaire pour que lesson.id soit visible aux inserts enfants ci-dessous

        for pos, label in enumerate(l.get("objectives", [])):
            db.add(LessonObjective(lesson_id=lesson.id, position=pos, label=label))

        for pos, sec in enumerate(l.get("sections", [])):
            db.add(LessonSection(lesson_id=lesson.id, position=pos, title=sec["title"], body=sec["body"]))

        depth = l.get("depth") or {}
        for key, content in depth.items():
            if not content:
                continue
            db.add(LessonDepthLevel(
                lesson_id=lesson.id,
                depth_key=DEPTH_KEY_MAP[key],
                label=DEPTH_LABELS_FR[key],
                title=content.get("title", DEPTH_LABELS_FR[key]),
                body=content.get("body", ""),
            ))
    db.flush()
    print(f"  lessons: {created} nouvelles créées sur {len(data['lessons'])} au total dans le prototype "
          f"(les leçons déjà en base ne sont plus retouchées)")


def seed_labs(db: Session, data: dict) -> None:
    """Labs hérités du prototype (texte simple, sans schéma interactif).
    Archivés (pas supprimés : conserve les soumissions déjà faites dessus) au
    profit des labs interactifs de seed_interactive_labs — cf. refonte de la
    section Labs. Le statut ARCHIVED les retire de /api/labs et /api/labs/{id}
    (filtrés sur PUBLISHED, cf. ContentRepository) sans perdre les données."""
    for l in data["labs"]:
        lab = _get_or_create(
            db, Lab, l["id"],
            school_id=l.get("schoolId"), title=l["title"], level=l.get("level"),
            duration_min=l.get("duration"), color=l.get("color"), description=l.get("description"),
            status=ContentStatus.ARCHIVED,
        )
        db.flush()

        for skill_id in l.get("skills", []):
            exists = db.execute(
                lab_skills.select().where(lab_skills.c.lab_id == lab.id, lab_skills.c.skill_id == skill_id)
            ).first()
            if not exists:
                db.execute(lab_skills.insert().values(lab_id=lab.id, skill_id=skill_id))

        for mode in l.get("modes", []):
            exists = db.execute(
                lab_modes.select().where(lab_modes.c.lab_id == lab.id, lab_modes.c.mode == mode)
            ).first()
            if not exists:
                db.execute(lab_modes.insert().values(lab_id=lab.id, mode=mode))
    db.flush()
    print(f"  labs: {len(data['labs'])}")


# Contenu original (pas issu du prototype CASA_DATA / casa_data.json) :
# premier lab au format « schéma interactif », sujet pilote de la refonte
# progressive des labos. Sources techniques : cf. discussion de conception,
# pipeline vérifié auprès de plusieurs synthèses techniques à jour sur
# l'inférence LLM (tokenisation BPE, embeddings + encodage positionnel,
# attention multi-têtes, prefill/KV cache, décodage autorégressif).
_LLM_PIPELINE_STEPS = [
    {
        "key": "reception",
        "title": "Réception de la requête",
        "summary": "Le message de l'utilisateur arrive côté serveur, accompagné du contexte de la conversation.",
        "detail": (
            "Avant même de parler du modèle, la requête transite par une API. Le serveur assemble le "
            "prompt final : le message de l'utilisateur, mais aussi l'historique de la conversation, "
            "les instructions système (le rôle donné à l'assistant) et, pour un système RAG, des "
            "extraits de documents récupérés au préalable. Ce prompt complet est ensuite envoyé au "
            "moteur d'inférence."
        ),
        "highlights": [
            "Le prompt envoyé au modèle n'est presque jamais le seul message tapé par l'utilisateur.",
            "Historique, instructions système et contexte récupéré (RAG) sont concaténés avant tokenisation.",
        ],
    },
    {
        "key": "tokenization",
        "title": "Tokenisation",
        "summary": "Le texte brut est découpé en tokens — pas des mots, des fragments.",
        "detail": (
            "Un tokenizer (le plus souvent basé sur le Byte Pair Encoding, BPE) découpe le texte en "
            "unités appelées tokens : un mot courant, un sous-mot, un signe de ponctuation ou même un "
            "fragment de mot rare. Chaque token est ensuite remplacé par un identifiant numérique "
            "unique, tiré d'un vocabulaire fixe (souvent 50 000 à plus de 100 000 tokens selon le "
            "modèle). Un mot rare ou un mot dans une langue peu représentée peut être découpé en "
            "plusieurs tokens."
        ),
        "highlights": [
            "« anticonstitutionnellement » peut devenir 4 ou 5 tokens, « le » en devient un seul.",
            "Le nombre de tokens détermine le coût et la limite de contexte d'une requête, pas le nombre de caractères.",
        ],
    },
    {
        "key": "embeddings",
        "title": "Embeddings et position",
        "summary": "Chaque identifiant de token devient un vecteur numérique dense, situé dans l'espace du sens.",
        "detail": (
            "Chaque token (un simple entier) est converti en un vecteur de plusieurs centaines à "
            "plusieurs milliers de dimensions, appris pendant l'entraînement : c'est l'embedding. Des "
            "tokens au sens proche (« chat », « chaton », « féline ») ont des embeddings proches dans "
            "cet espace. Comme le Transformer ne perçoit pas nativement l'ordre des tokens, un "
            "encodage positionnel est ajouté à chaque vecteur pour indiquer sa place dans la séquence."
        ),
        "highlights": [
            "Un embedding capture le sens statistique d'un token, pas sa définition de dictionnaire.",
            "Sans encodage positionnel, « le chat mange la souris » et « la souris mange le chat » seraient indiscernables.",
        ],
    },
    {
        "key": "attention",
        "title": "Attention et blocs Transformer",
        "summary": "Chaque token « regarde » tous les autres pour affiner sa représentation, couche après couche.",
        "detail": (
            "La séquence de vecteurs traverse plusieurs dizaines de blocs Transformer identiques. Dans "
            "chacun, le mécanisme d'auto-attention (multi-head self-attention) permet à chaque token "
            "de pondérer l'importance de tous les autres tokens du contexte pour mettre à jour sa "
            "propre représentation. Les premières couches captent des motifs de surface (syntaxe, "
            "tokens voisins) ; les couches profondes construisent des représentations plus abstraites "
            "(raisonnement, relations entre concepts éloignés dans le texte)."
        ),
        "highlights": [
            "« Multi-têtes » : plusieurs mécanismes d'attention tournent en parallèle, chacun capturant un type de relation différent.",
            "C'est cette étape, répétée sur des dizaines de couches, qui consomme l'essentiel du calcul.",
        ],
    },
    {
        "key": "prefill",
        "title": "Prefill et cache clé-valeur (KV cache)",
        "summary": "Le prompt entier est traité en un seul passage, et les résultats intermédiaires sont mis en cache.",
        "detail": (
            "Lors du prefill, l'intégralité du prompt (tous les tokens de la requête) est encodée en "
            "une seule fois à travers les blocs Transformer. Pour chaque token, chaque couche calcule "
            "et conserve deux vecteurs — clé et valeur — dans un cache appelé KV cache. Ce cache évite "
            "de recalculer l'attention sur tout l'historique à chaque nouveau token généré : sans lui, "
            "générer une réponse de N tokens coûterait un calcul proportionnel à N² ; avec lui, il "
            "devient proportionnel à N."
        ),
        "highlights": [
            "Le prefill est la phase la plus gourmande en calcul brut (beaucoup de tokens traités d'un coup).",
            "Le KV cache est ce qui rend une conversation longue exploitable sans exploser le temps de réponse.",
        ],
    },
    {
        "key": "decoding",
        "title": "Décodage et échantillonnage",
        "summary": "Le modèle génère la réponse un token à la fois, en choisissant parmi les candidats les plus probables.",
        "detail": (
            "Après le prefill vient le décodage, autorégressif : à chaque étape, le modèle produit une "
            "distribution de probabilité sur tout le vocabulaire pour le prochain token, réutilise le "
            "KV cache existant, puis un mécanisme d'échantillonnage (température, top-k, top-p) choisit "
            "le token suivant — pas toujours le plus probable, pour éviter des réponses mécaniques et "
            "répétitives. Le token choisi est ajouté au contexte, son propre couple clé-valeur rejoint "
            "le cache, et le cycle recommence pour le token suivant."
        ),
        "highlights": [
            "Une température basse rend la sortie plus déterministe ; une température élevée la rend plus créative (et plus risquée).",
            "Chaque token généré déclenche un nouveau passage dans tous les blocs Transformer.",
        ],
    },
    {
        "key": "detokenization",
        "title": "Détokenisation et réponse",
        "summary": "Les tokens générés sont reconvertis en texte lisible, envoyé au fur et à mesure à l'utilisateur.",
        "detail": (
            "Chaque token produit par le décodage est immédiatement retraduit en texte grâce au "
            "vocabulaire du tokenizer, puis renvoyé à l'utilisateur — souvent en streaming, morceau "
            "par morceau, ce qui explique l'effet de « texte qui s'affiche progressivement » dans la "
            "plupart des interfaces de chat. Le cycle de décodage s'arrête quand le modèle génère un "
            "token spécial de fin de séquence, ou qu'une limite de longueur est atteinte."
        ),
        "highlights": [
            "Le streaming n'est pas un effet cosmétique : c'est littéralement l'ordre dans lequel les tokens sortent du modèle.",
            "Un token de fin de séquence (EOS) est ce qui signale au modèle « j'ai fini de répondre ».",
        ],
    },
]


_DATA_PIPELINE_STEPS = [
    {
        "key": "ingestion",
        "title": "Ingestion : faire entrer la donnée",
        "summary": "Les données brutes entrent dans le système, en flux continu ou par lots.",
        "detail": (
            "Tout commence par la collecte : bases de données transactionnelles, API externes, "
            "capteurs IoT, journaux d'application. L'ingestion par lots (batch) convient aux volumes "
            "prévisibles et périodiques ; l'ingestion en flux (streaming) capte les événements en "
            "continu. Une technique comme le Change Data Capture (CDC) permet de ne synchroniser que "
            "ce qui a changé dans une source, sans tout recharger."
        ),
        "highlights": [
            "Batch = simple et prévisible ; streaming = données à jour en continu, mais plus complexe à opérer.",
            "Le CDC évite de retraiter des téraoctets de données inchangées à chaque synchronisation.",
        ],
    },
    {
        "key": "transformation",
        "title": "Transformation : nettoyer, structurer, enrichir",
        "summary": "La donnée brute devient exploitable : dédupliquée, standardisée, validée.",
        "detail": (
            "C'est l'étape où la donnée brute (souvent désordonnée, incomplète, incohérente) est "
            "transformée : suppression des doublons, uniformisation des formats (dates, unités, "
            "encodages), enrichissement par croisement avec d'autres sources. Les outils modernes de "
            "type ELT poussent cette transformation directement sur la puissance de calcul du cloud, "
            "plutôt que de tout transformer avant chargement."
        ),
        "highlights": [
            "ETL transforme avant de charger ; ELT charge d'abord, puis transforme à l'échelle du cloud.",
            "Une transformation mal faite ici contamine silencieusement tout ce qui est construit dessus.",
        ],
    },
    {
        "key": "storage",
        "title": "Stockage : du lac de données au lakehouse",
        "summary": "La donnée transformée est organisée en couches, du brut au prêt-à-l'emploi.",
        "detail": (
            "L'architecture en couches (souvent appelée architecture médaillon) organise le stockage "
            "en trois niveaux : Bronze (donnée brute telle qu'ingérée, traçabilité complète), Silver "
            "(donnée nettoyée et validée), Gold (donnée agrégée, prête pour l'analyse ou l'entraînement "
            "de modèles). Le lakehouse combine la flexibilité d'un data lake et les garanties de "
            "fiabilité d'un entrepôt de données classique."
        ),
        "highlights": [
            "Garder la couche Bronze intacte permet de retraiter différemment si une erreur est découverte plus tard.",
            "La couche Gold est ce que voient la plupart des équipes data science et IA, jamais le brut.",
        ],
    },
    {
        "key": "quality",
        "title": "Qualité : détecter avant que ça ne casse en aval",
        "summary": "Des règles de validation vérifient la donnée à chaque étape, pas seulement à la fin.",
        "detail": (
            "La qualité de la donnée se pilote par des règles explicites — complétude, exactitude, "
            "cohérence, fraîcheur — vérifiées automatiquement à chaque étape du pipeline plutôt que "
            "découvertes a posteriori par un modèle qui se comporte mal. Une donnée qui échoue à ces "
            "contrôles est isolée avant d'atteindre les couches suivantes."
        ),
        "highlights": [
            "Une règle de qualité définie une fois protège tous les usages futurs de cette donnée, y compris ceux non encore imaginés.",
            "Détecter un problème de qualité au niveau du pipeline coûte bien moins cher que de le découvrir dans les prédictions d'un modèle en production.",
        ],
    },
    {
        "key": "catalog_governance",
        "title": "Catalogage et gouvernance",
        "summary": "Chaque jeu de données est documenté, tracé et soumis à des règles d'accès.",
        "detail": (
            "Un catalogue de données centralise les métadonnées : qui a produit cette donnée, quand, à "
            "partir de quelles sources (lignage), qui a le droit d'y accéder, quelle est sa définition "
            "métier. C'est ce qui rend un pipeline auditable — capable de répondre à « d'où vient cette "
            "donnée » et « qui peut la voir » — plutôt qu'une boîte noire. C'est le pont direct vers la "
            "gouvernance des données (cf. lab dédié)."
        ),
        "highlights": [
            "Sans lignage documenté, une erreur découverte en Gold est presque impossible à remonter jusqu'à sa source.",
            "Le catalogage est ce qui permet à une équipe IA de découvrir qu'un jeu de données existe déjà, sans le recréer en double.",
        ],
    },
    {
        "key": "serving",
        "title": "Mise à disposition : nourrir modèles et décisions",
        "summary": "La donnée prête est servie aux modèles d'IA, aux tableaux de bord et aux applications.",
        "detail": (
            "En bout de chaîne, la donnée Gold est exposée via des interfaces adaptées à chaque usage : "
            "un feature store pour l'entraînement de modèles, des vues analytiques pour les tableaux de "
            "bord, des API pour les applications. C'est cette dernière étape qui referme la boucle : un "
            "pipeline de données n'a de valeur que par ce qu'il permet de construire derrière — y "
            "compris, de plus en plus, l'entraînement et l'inférence de modèles d'IA."
        ),
        "highlights": [
            "Un feature store garantit que le même calcul de variable est utilisé à l'entraînement et en production — une source fréquente de bugs silencieux quand ce n'est pas le cas.",
            "C'est ici que le pipeline de données rejoint directement le sujet « données comme carburant de l'IA ».",
        ],
    },
]

_DATA_GOVERNANCE_STEPS = [
    {
        "key": "stewardship",
        "title": "Propriété et responsabilité (data stewardship)",
        "summary": "Chaque donnée a un propriétaire identifié, responsable de sa qualité et de son usage.",
        "detail": (
            "Une gouvernance efficace commence par des rôles clairs : un sponsor exécutif fixe le cap, "
            "un responsable des données (souvent un Chief Data Officer) porte le programme, des "
            "propriétaires de données ont le pouvoir de décision sur un domaine (ex: données clients, "
            "données RH), et des stewards (intendants) gèrent au quotidien la qualité et les "
            "définitions. Sans cette chaîne de responsabilité, personne n'est jamais clairement en tort "
            "quand une donnée est fausse ou mal utilisée."
        ),
        "highlights": [
            "« Tout le monde est responsable » revient en pratique à « personne n'est responsable ».",
            "Le propriétaire d'un domaine de données n'est pas forcément dans l'équipe IT — souvent un responsable métier.",
        ],
    },
    {
        "key": "quality_policy",
        "title": "Qualité comme politique, pas comme incident",
        "summary": "La qualité des données est définie par des règles écrites, pas découverte après coup.",
        "detail": (
            "La gouvernance formalise ce que « bonne qualité » signifie pour chaque type de donnée — "
            "exactitude, complétude, cohérence, fraîcheur — et fixe des seuils acceptables. Cela "
            "transforme la qualité d'un problème réactif (« pourquoi ce modèle se trompe ») en une "
            "politique proactive vérifiée en continu."
        ),
        "highlights": [
            "Une donnée peut être « techniquement correcte » et quand même violer une règle de gouvernance (ex: âge négatif, email sans @).",
            "Les règles de qualité gouvernées sont documentées une fois, appliquées partout.",
        ],
    },
    {
        "key": "security_privacy",
        "title": "Sécurité et confidentialité",
        "summary": "Contrôles d'accès, chiffrement et minimisation protègent les données sensibles.",
        "detail": (
            "La gouvernance définit qui peut voir, modifier ou exporter chaque catégorie de donnée — en "
            "particulier les données personnelles ou sensibles. Cela passe par le contrôle d'accès (qui "
            "a le droit), le chiffrement (au repos et en transit), et le principe de minimisation : ne "
            "collecter et ne conserver que ce qui est réellement nécessaire."
        ),
        "highlights": [
            "Une donnée d'entraînement d'un modèle IA reste soumise aux mêmes règles de confidentialité que n'importe quelle autre donnée.",
            "Le principe de minimisation réduit aussi la surface d'exposition en cas de fuite.",
        ],
    },
    {
        "key": "compliance",
        "title": "Conformité réglementaire",
        "summary": "Les règles internes doivent s'aligner sur les obligations légales (RGPD et équivalents sectoriels).",
        "detail": (
            "Au-delà des règles internes, la gouvernance doit démontrer une conformité active aux "
            "réglementations en vigueur — RGPD en Europe, et des cadres équivalents ou sectoriels "
            "ailleurs. En 2026, les attentes réglementaires portent sur des mesures de gouvernance des "
            "données et de l'IA réellement en place et démontrables, pas seulement des politiques "
            "écrites sur le papier."
        ),
        "highlights": [
            "« On a une politique » ne suffit plus : il faut pouvoir prouver que la politique est appliquée.",
            "Les cadres de gouvernance de l'IA (ex: gestion des risques) s'appuient directement sur les mêmes briques : inventaire, lignage, propriété, qualité.",
        ],
    },
    {
        "key": "lineage_catalog",
        "title": "Traçabilité, lignage et catalogue",
        "summary": "Un catalogue documente chaque donnée : son origine, ses transformations, ses usages autorisés.",
        "detail": (
            "Le lignage retrace le chemin complet d'une donnée depuis sa source jusqu'à son usage "
            "final, à travers toutes ses transformations. Combiné à un catalogue de métadonnées "
            "(définitions métier, propriétaire, sensibilité), il rend la gouvernance opérationnelle "
            "plutôt que théorique : n'importe qui peut retrouver l'origine d'un chiffre, et vérifier "
            "s'il a le droit de l'utiliser."
        ),
        "highlights": [
            "Le lignage permet de répondre à « si je corrige cette source, qu'est-ce que ça impacte en aval » avant de casser quelque chose.",
            "Un catalogue à jour évite qu'une même donnée soit redéfinie différemment par deux équipes.",
        ],
    },
]

_AI_TYPES_STEPS = [
    {
        "key": "narrow_ai_rules",
        "title": "L'IA comme discipline, et les règles comme point de départ",
        "summary": "L'intelligence artificielle est le champ englobant ; les systèmes à règles en sont la forme la plus simple.",
        "detail": (
            "L'IA désigne, au sens large, tout système capable d'exécuter des tâches associées à "
            "l'intelligence humaine. La forme la plus simple — l'automatisation à base de règles — "
            "applique une logique explicite écrite par un humain (« si X alors Y »), sans apprentissage "
            "à partir de données. Elle reste incontournable pour des décisions stables et explicables, "
            "mais ne s'adapte pas à des situations non prévues à l'avance."
        ),
        "highlights": [
            "Un système à règles est prévisible à 100% — c'est sa force et sa limite.",
            "Beaucoup de systèmes « IA » en production sont en réalité de l'automatisation classique, pas de l'apprentissage.",
        ],
    },
    {
        "key": "machine_learning",
        "title": "Machine learning : apprendre des relations à partir de données",
        "summary": "Plutôt que d'écrire les règles, on les fait apprendre au système à partir d'exemples.",
        "detail": (
            "Le machine learning est une approche spécifique au sein de l'IA : au lieu de coder des "
            "règles, on entraîne un modèle statistique sur des données d'exemple pour qu'il apprenne à "
            "généraliser. Il couvre des tâches comme la classification, la régression ou le clustering, "
            "avec des familles de modèles variées (arbres de décision, forêts aléatoires, méthodes à "
            "vecteurs de support...) — pas seulement les réseaux neuronaux."
        ),
        "highlights": [
            "Le ML classique reste souvent plus rapide, plus interprétable et suffisant pour de nombreux problèmes structurés.",
            "Le deep learning n'est qu'une des familles possibles à l'intérieur du machine learning.",
        ],
    },
    {
        "key": "deep_learning",
        "title": "Deep learning : des réseaux de neurones à plusieurs couches",
        "summary": "Une sous-famille du machine learning, capable de repérer des motifs complexes dans des données non structurées.",
        "detail": (
            "Le deep learning est un sous-ensemble du machine learning qui utilise des réseaux de "
            "neurones à de nombreuses couches pour reconnaître des motifs complexes — particulièrement "
            "efficace sur des données non structurées : images, son, texte. C'est la brique technique "
            "derrière la vision par ordinateur, le traitement du langage naturel, et les modèles "
            "génératifs modernes."
        ),
        "highlights": [
            "« Deep » fait référence au nombre de couches du réseau, pas à une quelconque profondeur conceptuelle.",
            "Plus un problème est non structuré (image brute, texte libre), plus le deep learning tend à surpasser le ML classique.",
        ],
    },
    {
        "key": "transformers_llm",
        "title": "Transformeurs et grands modèles de langage (LLM)",
        "summary": "Une architecture de deep learning spécialisée, à la base de tous les grands modèles de langage actuels.",
        "detail": (
            "La chaîne complète est : machine learning → deep learning → réseaux Transformer → grands "
            "modèles de langage (LLM). L'architecture Transformer, construite autour du mécanisme "
            "d'attention, a permis d'entraîner des modèles de langage à une échelle inédite. Un LLM est "
            "donc un type précis de modèle de deep learning, spécialisé dans le langage — pas un "
            "synonyme de « IA » en général."
        ),
        "highlights": [
            "Tous les LLM sont des modèles de deep learning, mais tous les modèles de deep learning ne sont pas des LLM (vision, audio, multimodal...).",
            "L'architecture Transformer sert aussi hors du texte : image, audio, protéines.",
        ],
    },
    {
        "key": "generative_vs_predictive",
        "title": "IA générative et IA prédictive : produire vs anticiper",
        "summary": "La différence n'est pas la technologie, c'est la nature de la sortie.",
        "detail": (
            "L'IA prédictive analyse des données pour anticiper un résultat (un risque de défaut de "
            "paiement, une probabilité de churn). L'IA générative, elle, produit un contenu nouveau — "
            "texte, image, code, audio — plutôt qu'une simple valeur ou catégorie. Un même modèle "
            "Transformer peut, selon la façon dont il est entraîné et utilisé, servir l'un ou l'autre de "
            "ces objectifs."
        ),
        "highlights": [
            "Générative = ce que le système produit ; prédictive = ce que le système anticipe.",
            "La distinction porte sur l'usage, pas nécessairement sur l'architecture sous-jacente.",
        ],
    },
    {
        "key": "agentic_ai",
        "title": "IA agentique : au-dessus des modèles, l'action autonome",
        "summary": "Les agents orchestrent un ou plusieurs modèles, des outils et une mémoire pour atteindre un objectif de façon autonome.",
        "detail": (
            "L'IA agentique se situe à la couche applicative, au-dessus des modèles : elle orchestre "
            "raisonnement (souvent porté par un LLM), appel d'outils externes, mémoire et enchaînement "
            "d'étapes pour poursuivre un objectif de façon autonome, sans qu'un humain valide chaque "
            "action intermédiaire. La différence clé avec l'IA générative classique est là : générative "
            "décrit ce qu'un système produit, agentique décrit comment un système agit."
        ),
        "highlights": [
            "Un agent peut combiner plusieurs modèles (un pour raisonner, un pour la vision, un pour la génération) et des outils non-IA (calculatrice, recherche web, base de données).",
            "Plus un système est autonome, plus le contrôle et la gouvernance de ses actions deviennent critiques.",
        ],
    },
]

_DATA_FUEL_STEPS = [
    {
        "key": "gigo",
        "title": "Garbage in, garbage out",
        "summary": "La qualité d'un modèle ne peut jamais dépasser la qualité des données qui l'ont entraîné.",
        "detail": (
            "Le principe « garbage in, garbage out » est fondamental : un modèle entraîné sur des "
            "données médiocres produira des résultats médiocres, quelle que soit la sophistication de "
            "son architecture. Comme le résume Andrew Ng, si 80% du travail d'une équipe IA est la "
            "préparation des données, alors garantir leur qualité est la tâche la plus critique de tout "
            "le projet — pas un détail secondaire."
        ),
        "highlights": [
            "Un modèle plus puissant entraîné sur de mauvaises données produit de mauvais résultats plus vite, pas de meilleurs résultats.",
            "Améliorer la qualité des données bat souvent, à effort égal, l'amélioration de l'architecture du modèle.",
        ],
    },
    {
        "key": "representativeness_bias",
        "title": "Représentativité et biais",
        "summary": "Un modèle reproduit fidèlement les déséquilibres présents dans ses données d'entraînement.",
        "detail": (
            "Le biais apparaît quand les données ne représentent pas fidèlement la population ou les "
            "situations réelles sur lesquelles le modèle sera utilisé. Un jeu de données de conduite "
            "mal équilibré en conditions de nuit ou de pluie produira un système de conduite autonome "
            "moins fiable dans ces conditions précises — un exemple où l'erreur de données devient un "
            "risque réel une fois déployée."
        ),
        "highlights": [
            "Un modèle n'invente pas de biais : il amplifie fidèlement ceux déjà présents dans ses données.",
            "La sous-représentation d'un cas dans les données d'entraînement se traduit directement en sous-performance sur ce cas en production.",
        ],
    },
    {
        "key": "volume_diversity",
        "title": "Volume, diversité et fraîcheur",
        "summary": "Plus de données aide, mais seulement si elles sont variées et à jour.",
        "detail": (
            "Le volume de données seul ne suffit pas : un très grand jeu de données peu diversifié "
            "reproduit les mêmes angles morts à grande échelle. La diversité (sources, contextes, "
            "populations représentées) et la fraîcheur (les données reflètent-elles encore la réalité "
            "actuelle) comptent autant que la quantité brute pour la capacité du modèle à généraliser "
            "correctement."
        ),
        "highlights": [
            "Doubler le volume de données similaires n'apporte souvent presque rien ; diversifier les sources, si.",
            "Un modèle entraîné sur des données périmées « désapprend » silencieusement la réalité actuelle — d'où le besoin de réentraînement régulier.",
        ],
    },
    {
        "key": "training_vs_inference",
        "title": "Deux moments où la donnée compte : entraînement et inférence",
        "summary": "La donnée alimente le modèle une première fois à l'entraînement, puis à chaque requête en inférence.",
        "detail": (
            "La donnée joue un rôle à deux moments distincts : à l'entraînement, un immense volume de "
            "données façonne les paramètres internes du modèle une fois pour toutes (ou jusqu'au "
            "prochain réentraînement). En inférence, chaque nouvelle requête est elle-même une donnée — "
            "le prompt, le contexte, les documents récupérés (RAG) — qui influence directement la "
            "réponse produite, sans modifier le modèle lui-même."
        ),
        "highlights": [
            "Un modèle « sait » ce qu'il a appris à l'entraînement, mais un système RAG peut lui apporter une donnée fraîche au moment de la requête, sans réentraînement.",
            "Confondre les deux moments (entraînement vs inférence) est une source fréquente de malentendus sur ce qu'un modèle « sait » vraiment.",
        ],
    },
    {
        "key": "feedback_loop",
        "title": "La boucle : les décisions du modèle redeviennent des données",
        "summary": "Ce qu'un modèle en production produit devient souvent, à son tour, une donnée d'entraînement future.",
        "detail": (
            "Une fois déployé, un modèle génère des décisions, des réponses, des interactions "
            "utilisateur — qui sont elles-mêmes collectées et peuvent alimenter la prochaine version du "
            "modèle. Cette boucle de rétroaction est puissante (elle permet l'amélioration continue) "
            "mais aussi risquée : si les erreurs ou biais du modèle en production sont réinjectés sans "
            "filtre dans les données d'entraînement suivantes, ils peuvent s'amplifier au fil des "
            "cycles plutôt que se corriger."
        ),
        "highlights": [
            "Une boucle de rétroaction mal surveillée peut transformer un petit biais initial en dérive importante après plusieurs cycles.",
            "C'est pourquoi la gouvernance des données (cf. lab dédié) ne s'arrête pas à l'entraînement — elle doit couvrir aussi les données produites en production.",
        ],
    },
]

_RAG_PIPELINE_STEPS = [
    {
        "key": "ingestion_chunking",
        "title": "Ingestion et découpage en chunks",
        "summary": "Les documents source sont nettoyés puis découpés en fragments exploitables.",
        "detail": (
            "Avant toute recherche, les documents (PDF, pages web, wikis internes) sont nettoyés, "
            "normalisés dans un format texte homogène, puis découpés en chunks — des fragments assez "
            "petits pour rester pertinents, assez grands pour garder du sens. Un découpage trop fin "
            "perd le contexte, trop large dilue la pertinence."
        ),
        "highlights": [
            "Le découpage détermine directement la qualité de tout ce qui suit — un mauvais chunk ne sera jamais bien retrouvé.",
            "Un chunk garde généralement une trace de sa provenance (document, section) pour permettre la citation.",
        ],
    },
    {
        "key": "embedding_indexing",
        "title": "Vectorisation et indexation",
        "summary": "Chaque chunk est converti en vecteur et stocké dans une base vectorielle.",
        "detail": (
            "Un modèle d'embedding transforme chaque chunk en un vecteur numérique dense, capturant "
            "son sens. Ces vecteurs sont stockés dans une base vectorielle (comme pgvector), indexée "
            "pour permettre une recherche par similarité rapide même sur des millions de chunks."
        ),
        "highlights": [
            "Le même modèle d'embedding doit être utilisé pour indexer les documents et pour encoder les questions — sinon les vecteurs ne sont pas comparables.",
            "Réindexer devient nécessaire si on change de modèle d'embedding.",
        ],
    },
    {
        "key": "query_retrieval",
        "title": "Recherche : la question devient un vecteur",
        "summary": "La question de l'utilisateur est elle-même vectorisée, puis comparée à tous les chunks indexés.",
        "detail": (
            "Quand un utilisateur pose une question, elle est encodée avec le même modèle d'embedding "
            "que les documents, puis comparée par similarité (le plus souvent cosinus) à l'ensemble des "
            "vecteurs indexés. Les systèmes avancés combinent cette recherche vectorielle (sémantique) "
            "avec une recherche par mots-clés classique, pour ne pas rater une correspondance exacte "
            "qu'un vecteur seul manquerait."
        ),
        "highlights": [
            "La recherche hybride (vecteurs + mots-clés) compense les angles morts de chaque approche prise seule.",
            "Cette étape renvoie typiquement plusieurs dizaines de candidats, pas encore le résultat final.",
        ],
    },
    {
        "key": "reranking",
        "title": "Reranking : trier les candidats par pertinence réelle",
        "summary": "Un modèle plus précis (mais plus lent) reclasse les meilleurs candidats avant de les retenir.",
        "detail": (
            "La recherche vectorielle initiale est rapide mais approximative. Un modèle de reranking — "
            "souvent un cross-encoder, qui compare directement la question et chaque chunk candidat "
            "plutôt que leurs vecteurs séparés — recalcule un score de pertinence plus fiable sur ce "
            "sous-ensemble restreint, et ne garde que les meilleurs."
        ),
        "highlights": [
            "Le reranking est trop coûteux pour tourner sur des millions de chunks — d'où la première passe de recherche vectorielle qui réduit le champ.",
            "C'est souvent le reranking, pas la recherche initiale, qui fait la différence entre un RAG médiocre et un bon RAG.",
        ],
    },
    {
        "key": "context_building",
        "title": "Construction du contexte et augmentation du prompt",
        "summary": "Les chunks retenus sont assemblés avec la question dans un prompt enrichi.",
        "detail": (
            "Les chunks les plus pertinents, une fois sélectionnés, sont insérés dans le prompt envoyé "
            "au modèle de langage, aux côtés de la question originale et d'instructions (répondre "
            "uniquement à partir du contexte fourni, citer les sources). C'est cette étape qui "
            "« augmente » la génération : le modèle ne répond plus seulement depuis ce qu'il a appris à "
            "l'entraînement, mais depuis des sources fraîches et vérifiables fournies au moment de la "
            "requête."
        ),
        "highlights": [
            "Le prompt final peut aisément dépasser la question initiale de plusieurs milliers de tokens de contexte.",
            "Des instructions explicites (« si l'information n'est pas dans le contexte, dis-le ») réduisent le risque d'hallucination.",
        ],
    },
    {
        "key": "grounded_generation",
        "title": "Génération sourcée",
        "summary": "Le modèle produit une réponse ancrée dans les documents récupérés, avec citations.",
        "detail": (
            "Le modèle de langage génère sa réponse en s'appuyant sur le contexte fourni plutôt que sur "
            "sa seule mémoire d'entraînement, et peut citer les documents sources utilisés — ce qui "
            "permet à l'utilisateur de vérifier l'information. C'est ce mécanisme qui rend un système "
            "RAG plus fiable qu'un LLM seul sur des sujets récents, internes à une organisation, ou "
            "nécessitant une traçabilité."
        ),
        "highlights": [
            "Une réponse RAG reste toujours vulnérable à un mauvais retrieval en amont : citer une source non pertinente ne rend pas la réponse correcte.",
            "La traçabilité (quelle source a produit quelle affirmation) est ce qui distingue un RAG bien conçu d'un simple « copier-coller augmenté ».",
        ],
    },
]

_MLOPS_LIFECYCLE_STEPS = [
    {
        "key": "training",
        "title": "Entraînement : des données aux paramètres",
        "summary": "Le modèle apprend à partir de données d'entraînement, avec chaque expérimentation tracée.",
        "detail": (
            "L'entraînement transforme des données annotées en un modèle dont les paramètres internes "
            "ont été ajustés pour minimiser une fonction de perte. Une pratique MLOps mature commence "
            "avant même la première ligne de code d'entraînement : chaque expérimentation (données "
            "utilisées, hyperparamètres, code, résultat) est tracée, pour pouvoir comparer les runs et "
            "reproduire n'importe quel modèle plus tard."
        ),
        "highlights": [
            "Sans traçabilité des expérimentations, il devient impossible de savoir pourquoi un modèle en production diffère de la version testée en recherche.",
            "Le versionnement porte sur trois éléments à la fois : le code, les données et les paramètres du modèle.",
        ],
    },
    {
        "key": "evaluation",
        "title": "Évaluation : mesurer avant de faire confiance",
        "summary": "Le modèle est confronté à des critères objectifs avant d'être jugé prêt.",
        "detail": (
            "Avant tout déploiement, le modèle est évalué contre des métriques définies à l'avance et "
            "des jeux de données de test jamais vus à l'entraînement. Cette évaluation se poursuit "
            "après le déploiement : la performance d'un modèle en production est réévaluée en continu, "
            "pour repérer le moment où il doit être remplacé plutôt que de laisser sa qualité se "
            "dégrader silencieusement."
        ),
        "highlights": [
            "Une bonne performance sur les données d'entraînement ne garantit rien sur des données jamais vues (surapprentissage).",
            "L'évaluation ne s'arrête jamais au premier déploiement — c'est un contrôle continu, pas une étape ponctuelle.",
        ],
    },
    {
        "key": "deployment",
        "title": "Déploiement : mettre en production progressivement",
        "summary": "Le nouveau modèle est mis en service graduellement, jamais d'un seul coup pour tout le monde.",
        "detail": (
            "Le déploiement moderne évite le tout-ou-rien : des techniques de livraison progressive — "
            "activation par flag pour un sous-ensemble d'utilisateurs, tests champion/challenger "
            "comparant l'ancien et le nouveau modèle en parallèle, déploiements graduels — permettent "
            "de détecter un problème avant qu'il n'affecte tout le monde, et de revenir en arrière "
            "rapidement si besoin."
        ),
        "highlights": [
            "Un déploiement progressif transforme une erreur de modèle en incident mineur plutôt qu'en panne générale.",
            "Le modèle « champion » actuel et un modèle « challenger » candidat peuvent tourner en parallèle avant de faire basculer tout le trafic.",
        ],
    },
    {
        "key": "monitoring",
        "title": "Supervision : détecter avant que l'utilisateur ne s'en aperçoive",
        "summary": "Le comportement du modèle en production est surveillé en continu, pas seulement sa disponibilité technique.",
        "detail": (
            "La supervision d'un modèle en production va au-delà du monitoring technique classique (le "
            "service répond-il) : elle surveille la distribution des données reçues, la dérive par "
            "rapport aux données d'entraînement, et les indicateurs de qualité des prédictions. C'est "
            "ce qui permet de détecter tôt un problème, ce qui construit la confiance, et ce qui permet "
            "de planifier les évolutions du système à mesure que le contexte change."
        ),
        "highlights": [
            "Un modèle peut rester techniquement « en ligne » tout en étant devenu silencieusement peu fiable — c'est précisément ce que la supervision de la dérive doit attraper.",
            "Les alertes de supervision doivent porter sur la qualité des prédictions, pas seulement sur la disponibilité du service.",
        ],
    },
    {
        "key": "retraining",
        "title": "Réentraînement : fermer la boucle",
        "summary": "Un signal de dérive ou de dégradation déclenche un nouveau cycle d'entraînement.",
        "detail": (
            "Quand la supervision détecte qu'un seuil de dérive ou de dégradation de performance est "
            "franchi, cela déclenche un nouveau cycle d'entraînement — avec des données plus récentes, "
            "éventuellement enrichies des cas d'erreur repérés en production. Le cycle de vie d'un "
            "modèle n'est donc pas une liste linéaire à cocher une fois, mais une boucle continue : "
            "entraînement, évaluation, déploiement, supervision, réentraînement, et ainsi de suite."
        ),
        "highlights": [
            "En 2026, le succès d'un système de machine learning ne se mesure plus seulement à la précision du modèle, mais à sa fiabilité, sa capacité à passer à l'échelle et sa gouvernance dans la durée.",
            "Ne pas fermer cette boucle est la cause la plus fréquente de modèles qui « fonctionnaient bien au début » et se dégradent silencieusement.",
        ],
    },
]

_AI_AGENTS_STEPS = [
    {
        "key": "goal_perception",
        "title": "Objectif et perception : comprendre la demande",
        "summary": "L'agent reçoit un objectif et le contexte initial nécessaire pour commencer à agir.",
        "detail": (
            "Tout commence par la définition d'un objectif — une tâche à accomplir, pas juste une "
            "question à répondre — et la perception du contexte disponible : message de l'utilisateur, "
            "état actuel du système, contraintes à respecter. C'est cette différence qui distingue un "
            "agent d'un simple assistant conversationnel : l'agent est censé agir pour atteindre un "
            "résultat, pas seulement répondre."
        ),
        "highlights": [
            "Un objectif mal défini au départ produit un agent qui agit, mais pas dans la bonne direction.",
            "La perception inclut souvent l'état du monde extérieur (fichiers, API, base de données), pas seulement le message reçu.",
        ],
    },
    {
        "key": "reasoning_planning",
        "title": "Raisonnement et planification",
        "summary": "Un modèle de langage décompose l'objectif en une suite d'étapes concrètes.",
        "detail": (
            "La couche de raisonnement — le plus souvent portée par un grand modèle de langage — "
            "interprète l'objectif et planifie une séquence d'actions pour l'atteindre. Deux approches "
            "dominent : le raisonnement dynamique pas-à-pas (le cycle ReAct : réfléchir, agir, "
            "observer, recommencer), adapté aux tâches imprévisibles ; et la planification à l'avance "
            "de toute la séquence avant d'agir, plus adaptée à des workflows prévisibles."
        ),
        "highlights": [
            "ReAct s'adapte mieux à l'imprévu, mais coûte plus cher (plus d'allers-retours avec le modèle).",
            "Planifier tout à l'avance est plus rapide et plus contrôlable, mais casse si la réalité dévie du plan initial.",
        ],
    },
    {
        "key": "memory",
        "title": "Mémoire : court terme et long terme",
        "summary": "L'agent garde en tête le contexte de la session, et peut aussi se souvenir d'expériences passées.",
        "detail": (
            "La mémoire à court terme conserve le contexte de la session en cours (ce qui a déjà été "
            "essayé, dit, obtenu). La mémoire à long terme, elle, persiste au-delà d'une session — elle "
            "permet à l'agent de savoir qu'il a déjà tenté une recherche particulière et obtenu un "
            "mauvais résultat, ou qu'un appel API précis a déjà échoué, sans avoir à tout redécouvrir à "
            "chaque fois."
        ),
        "highlights": [
            "Sans mémoire à long terme, un agent répète indéfiniment les mêmes erreurs d'une session à l'autre.",
            "La mémoire long terme d'un agent s'appuie souvent directement sur un système RAG (cf. lab dédié) pour retrouver l'information pertinente.",
        ],
    },
    {
        "key": "tool_use",
        "title": "Utilisation d'outils : agir sur le monde réel",
        "summary": "L'agent appelle des API, des bases de données ou des fonctions pour agir au-delà de la simple génération de texte.",
        "detail": (
            "La couche d'intégration d'outils donne à l'agent accès à des API, bases de données, "
            "calculatrices, moteurs de recherche ou fonctions métier — tout ce qui lui permet d'agir "
            "concrètement plutôt que de seulement produire du texte. C'est ce qui transforme un modèle "
            "de langage, limité à générer des mots, en un système capable de consulter une vraie base "
            "de données ou d'envoyer un vrai email."
        ),
        "highlights": [
            "Un agent peut combiner plusieurs modèles spécialisés (un pour raisonner, un pour la vision) avec des outils non-IA classiques.",
            "Chaque outil ajouté est aussi une nouvelle surface de risque — un agent avec accès à trop d'outils est plus difficile à sécuriser et à auditer.",
        ],
    },
    {
        "key": "orchestration",
        "title": "Orchestration : coordonner la boucle plan → agir → observer",
        "summary": "Une couche de contrôle séquence les tâches, gère les erreurs et applique des limites.",
        "detail": (
            "La couche d'orchestration gère le flux de contrôle global : elle séquence les tâches, "
            "relance une action après un échec, applique des limites (nombre maximal d'étapes, budget, "
            "délai), et coordonne le raisonnement avec tout le reste — mémoire, outils, éventuellement "
            "d'autres agents dans un système multi-agents. C'est elle qui empêche un agent de boucler "
            "indéfiniment ou de dépasser silencieusement son mandat."
        ),
        "highlights": [
            "Sans limites explicites, un agent bloqué peut consommer un budget de calcul illimité en boucle sur une même erreur.",
            "Dans un système multi-agents, l'orchestration décide aussi quel agent spécialisé traite quelle partie de la tâche.",
        ],
    },
    {
        "key": "governance_oversight",
        "title": "Gouvernance et supervision humaine",
        "summary": "Plus un agent est autonome, plus le contrôle de ses actions devient critique.",
        "detail": (
            "Un agent capable d'agir sans validation humaine à chaque étape doit être encadré : "
            "journalisation de chaque action pour permettre l'audit, points de confirmation humaine "
            "avant les actions les plus sensibles (irréversibles, coûteuses, ou à fort impact), et "
            "limites claires sur ce qu'il est autorisé à faire seul. La réussite d'un système agentique "
            "en production ne se mesure pas qu'à son autonomie, mais à la confiance qu'on peut lui "
            "accorder sans supervision constante."
        ),
        "highlights": [
            "Une action irréversible (envoyer un email, supprimer une donnée, valider un paiement) mérite presque toujours une confirmation humaine explicite, quel que soit le niveau de confiance dans l'agent.",
            "L'audit après coup ne remplace pas le contrôle avant l'action — les deux sont nécessaires.",
        ],
    },
]

_INTERACTIVE_LABS = [
    {
        "id": "llm-request-pipeline", "school_id": "genai",
        "title": "Comprendre le pipeline d'une requête LLM",
        "level": "N2–N3", "duration_min": 40, "color": "#7C6BD0",
        "description": (
            "De votre message à la réponse générée : réception, tokenisation, embeddings, attention, "
            "prefill, décodage — explorez chaque étape du pipeline d'inférence d'un grand modèle de "
            "langage."
        ),
        "instructions": (
            "Parcourez les 7 étapes du pipeline, dans l'ordre ou en cliquant directement sur celle qui "
            "vous intéresse. Pour chaque étape, notez ce qui change de forme (texte → tokens → "
            "vecteurs → probabilités → texte) et ce qui est mis en cache ou réutilisé d'une étape à "
            "l'autre."
        ),
        "deliverable": (
            "Un court résumé (5 à 10 lignes) expliquant, avec vos propres mots, pourquoi le KV cache "
            "rend une conversation longue exploitable, et ce qui se passerait sans lui."
        ),
        "evaluation_note": (
            "Le résumé doit distinguer clairement le prefill (tout le prompt d'un coup) du décodage "
            "(un token à la fois), et expliquer le rôle du cache dans cette distinction."
        ),
        "steps": _LLM_PIPELINE_STEPS,
        "skills": ("transformers", "llm-foundations", "gpu-compute"),
    },
    {
        "id": "data-pipeline-explained", "school_id": "data",
        "title": "Le pipeline de la donnée, de la source au modèle",
        "level": "N1–N2", "duration_min": 35, "color": "#17B8C4",
        "description": (
            "Ingestion, transformation, stockage, qualité, catalogage, mise à disposition : suivez une "
            "donnée depuis sa source jusqu'à ce qu'elle nourrisse un modèle d'IA ou un tableau de bord."
        ),
        "instructions": (
            "Parcourez les 6 étapes du pipeline. Pour chacune, identifiez ce qui pourrait mal se passer "
            "si cette étape était sautée ou mal faite, et quel impact ça aurait sur les étapes "
            "suivantes."
        ),
        "deliverable": (
            "Choisissez une étape du pipeline et décrivez, en 5 lignes, un exemple concret de ce qui "
            "peut mal tourner si elle est négligée (à partir d'un cas que vous connaissez ou inventé)."
        ),
        "evaluation_note": "L'exemple doit être rattaché explicitement à l'étape choisie et à son impact en aval.",
        "steps": _DATA_PIPELINE_STEPS,
        "skills": ("data-architecture", "data-foundations", "data-governance"),
    },
    {
        "id": "data-governance-explained", "school_id": "governance",
        "title": "Gouvernance des données : qui décide, qui répond",
        "level": "N2–N3", "duration_min": 35, "color": "#16847A",
        "description": (
            "Propriété, qualité, sécurité, conformité, lignage : explorez les cinq piliers qui rendent "
            "une donnée gouvernée plutôt que simplement stockée."
        ),
        "instructions": (
            "Parcourez les 5 piliers de la gouvernance. Pour chacun, identifiez qui, dans une "
            "organisation type, en serait responsable (rôle, pas nom de personne)."
        ),
        "deliverable": (
            "Listez les 5 piliers avec, pour chacun, le rôle qui en serait typiquement responsable et "
            "une conséquence concrète si ce pilier est absent."
        ),
        "evaluation_note": "Chaque pilier doit avoir un rôle attribué et une conséquence réaliste, pas générique.",
        "steps": _DATA_GOVERNANCE_STEPS,
        "skills": ("data-governance", "ai-governance", "ai-regulation"),
    },
    {
        "id": "ai-types-landscape", "school_id": "culture",
        "title": "Panorama des types d'IA et modèles, et leurs relations",
        "level": "N1–N2", "duration_min": 35, "color": "#C47A16",
        "description": (
            "IA, machine learning, deep learning, Transformers, LLM, IA générative, IA agentique : "
            "démêlez la hiérarchie et les relations entre ces termes souvent confondus."
        ),
        "instructions": (
            "Parcourez les 6 étapes, de la discipline la plus large (l'IA) à la plus spécifique (les "
            "agents). Notez à chaque étape ce qui est « sous-ensemble de » quoi."
        ),
        "deliverable": (
            "Dessinez ou décrivez par écrit la hiérarchie complète (IA → ... → agents) avec, pour "
            "chaque flèche, un exemple concret de système réel."
        ),
        "evaluation_note": "La hiérarchie doit respecter l'ordre sous-ensemble/sur-ensemble présenté dans le schéma.",
        "steps": _AI_TYPES_STEPS,
        "skills": ("ai-literacy", "neural-networks", "llm-foundations"),
    },
    {
        "id": "data-fuel-for-ai", "school_id": "data",
        "title": "La donnée, carburant de l'IA",
        "level": "N1–N2", "duration_min": 30, "color": "#D8A23B",
        "description": (
            "Garbage in garbage out, biais, volume, entraînement vs inférence, boucle de rétroaction : "
            "comprenez pourquoi la qualité de la donnée détermine celle du modèle, avant même de "
            "parler d'architecture."
        ),
        "instructions": (
            "Parcourez les 5 étapes. Pour chacune, cherchez un exemple (réel ou plausible) tiré d'un "
            "domaine qui vous intéresse (santé, finance, transport, éducation...)."
        ),
        "deliverable": (
            "Choisissez un cas d'usage IA (réel ou fictif) et décrivez, pour ce cas précis, un risque "
            "de biais plausible lié à ses données d'entraînement, et une façon de le limiter."
        ),
        "evaluation_note": "Le risque décrit doit être spécifique au cas choisi, pas une généralité sur les biais en IA.",
        "steps": _DATA_FUEL_STEPS,
        "skills": ("data-foundations", "llm-training", "data-governance"),
    },
    {
        "id": "rag-question-to-answer", "school_id": "rag",
        "title": "RAG : de la question à la réponse sourcée",
        "level": "N2–N3", "duration_min": 40, "color": "#2FBF9F",
        "description": (
            "Ingestion, vectorisation, recherche, reranking, construction du contexte, génération "
            "sourcée : suivez le chemin complet d'une question dans un système RAG, du document brut à "
            "la réponse citée."
        ),
        "instructions": (
            "Parcourez les 6 étapes. Notez à chaque étape la nature de ce qui est manipulé (texte brut, "
            "vecteurs, scores, prompt, réponse) et ce qui distingue cette étape de la précédente."
        ),
        "deliverable": (
            "Expliquez en 5 à 10 lignes pourquoi une recherche vectorielle seule (sans reranking) peut "
            "renvoyer des chunks peu pertinents, et ce que le reranking corrige concrètement."
        ),
        "evaluation_note": "L'explication doit distinguer clairement le rôle de la recherche initiale et celui du reranking.",
        "steps": _RAG_PIPELINE_STEPS,
        "skills": ("rag-design", "knowledge-systems", "llm-foundations"),
    },
    {
        "id": "mlops-model-lifecycle", "school_id": "systems",
        "title": "Cycle de vie MLOps d'un modèle",
        "level": "N2–N3", "duration_min": 35, "color": "#6D5BD0",
        "description": (
            "Entraînement, évaluation, déploiement progressif, supervision, réentraînement : un modèle "
            "d'IA n'est jamais « fini » — explorez la boucle continue qui le maintient fiable en "
            "production."
        ),
        "instructions": (
            "Parcourez les 5 étapes. Pour chacune, identifiez quel signal déclenche le passage à "
            "l'étape suivante (ex: qu'est-ce qui déclenche un réentraînement ?)."
        ),
        "deliverable": (
            "Décrivez, pour un modèle de votre choix (réel ou fictif), un scénario de dérive détecté en "
            "supervision, et les étapes du cycle qu'il faudrait rejouer pour y répondre."
        ),
        "evaluation_note": "Le scénario doit citer explicitement quelles étapes du cycle sont rejouées, dans quel ordre.",
        "steps": _MLOPS_LIFECYCLE_STEPS,
        "skills": ("mlops", "ml-modeling", "ml-evaluation"),
    },
    {
        "id": "ai-agents-orchestration", "school_id": "agents",
        "title": "Agents IA : raisonnement, outils et orchestration",
        "level": "N2–N3", "duration_min": 40, "color": "#C47A16",
        "description": (
            "Objectif, raisonnement, mémoire, outils, orchestration, gouvernance : comprenez comment un "
            "agent décompose un objectif en actions, et où le contrôle humain doit rester dans la "
            "boucle."
        ),
        "instructions": (
            "Parcourez les 6 étapes. Pour chacune, identifiez ce qui pourrait mal tourner si cette "
            "couche était absente ou mal conçue."
        ),
        "deliverable": (
            "Décrivez un agent (réel ou fictif) et, pour lui, une action que vous jugeriez trop "
            "sensible pour être exécutée sans confirmation humaine — et pourquoi."
        ),
        "evaluation_note": "L'action choisie doit être concrète et la justification doit s'appuyer sur son caractère irréversible, coûteux ou à fort impact.",
        "steps": _AI_AGENTS_STEPS,
        "skills": ("agent-design", "multi-agent", "llm-foundations"),
    },
]


# Bibliographies de cours (§ enrichissement de contenu) : sources réellement
# utilisées pour rédiger le contenu enrichi de chaque cours, reliées via
# resource_courses (existait déjà en base, jamais reliée à aucune route API
# jusqu'ici — cf. discussion de conception). Contenu original, pas dérivé du
# prototype.
_COURSE_BIBLIOGRAPHIES = {
    "fundamentals": [
        {
            "id": "src-ai-taxonomy-toloka", "title": "Difference between AI, ML, LLM, and generative AI",
            "type": "Article", "publisher": "Toloka", "year": 2026,
            "url": "https://toloka.ai/blog/difference-between-ai-ml-llm-and-generative-ai/",
            "description": "Panorama de la hiérarchie IA → machine learning → deep learning → LLM et de la distinction générative/agentique.",
        },
        {
            "id": "src-ai-taxonomy-microsoft", "title": "Generative AI versus Different Types of AI",
            "type": "Explainer", "publisher": "Microsoft AI", "year": 2026,
            "url": "https://www.microsoft.com/en-us/ai/ai-101/generative-ai-vs-other-types-of-ai",
            "description": "Distinction entre IA générative et IA prédictive, et positionnement des agents.",
        },
        {
            "id": "src-decision-intelligence-tredence", "title": "What is Decision Intelligence? The Future of Data Science",
            "type": "Article", "publisher": "Tredence", "year": 2026,
            "url": "https://www.tredence.com/blog/decision-intelligence-future-of-data-science",
            "description": "Chaîne de valeur donnée → information → connaissance → décision, et son évolution vers la « decision intelligence ».",
        },
        {
            "id": "src-llm-hallucination-lakera", "title": "LLM Hallucinations: How to Understand and Tackle AI's Most Persistent Quirk",
            "type": "Guide", "publisher": "Lakera", "year": 2026,
            "url": "https://www.lakera.ai/blog/guide-to-hallucinations-in-large-language-models",
            "description": "Mécanisme des hallucinations des modèles génératifs et facteurs qui les aggravent.",
        },
        {
            "id": "src-llm-hallucination-keymakr", "title": "Preventing LLM Hallucinations: Best Practices",
            "type": "Guide", "publisher": "Keymakr", "year": 2026,
            "url": "https://keymakr.com/blog/preventing-llm-hallucinations-techniques-best-practices-2026/",
            "description": "Bonnes pratiques de vérification : ancrage par sources (RAG), citation explicite, validation humaine proportionnée au risque.",
        },
    ],
    "genai": [
        {
            "id": "src-tokenization-redis", "title": "Tokenization in LLMs: What AI App Devs Need to Know",
            "type": "Article", "publisher": "Redis", "year": 2026,
            "url": "https://redis.io/blog/tokenization-in-llms/",
            "description": "Fonctionnement du découpage en tokens (BPE) et impact sur le coût et la fenêtre de contexte.",
        },
        {
            "id": "src-prompt-engineering-anthropic", "title": "Prompt engineering best practices for 2026",
            "type": "Guide", "publisher": "Anthropic", "year": 2026,
            "url": "https://claude.com/blog/best-practices-for-prompt-engineering",
            "description": "Structure rôle/contexte/tâche/contraintes/format, contraintes explicites, exemples plutôt que descriptions.",
        },
        {
            "id": "src-llm-eval-openlayer", "title": "LLM evaluation metrics: Complete guide",
            "type": "Guide", "publisher": "Openlayer", "year": 2026,
            "url": "https://www.openlayer.com/blog/llm-evaluation-metrics-complete-guide",
            "description": "Panorama des dimensions d'évaluation d'un système LLM : exactitude, sécurité, coût, latence.",
        },
        {
            "id": "src-llm-eval-futureagi", "title": "Evaluating LLM Systems: Metrics and Benchmarks",
            "type": "Article", "publisher": "FutureAGI", "year": 2026,
            "url": "https://futureagi.com/blog/evaluating-llm-systems-metrics-benchmarks-2026/",
            "description": "Cadre en quatre piliers pour évaluer un système LLM : capacité, sécurité, expérience, opération.",
        },
    ],
    "usecases": [
        {
            "id": "src-usecase-prioritization-agility", "title": "AI Use Case Identification and Prioritization",
            "type": "Guide", "publisher": "Agility at Scale", "year": 2026,
            "url": "https://agility-at-scale.com/ai/strategy/ai-use-case-identification-and-prioritization/",
            "description": "Grille de priorisation valeur/faisabilité/risque/dépendances pour passer d'une liste d'idées à une feuille de route.",
        },
        {
            "id": "src-usecase-prioritization-fountaincity", "title": "How to Prioritize AI Projects: 5-Criteria Scoring Framework",
            "type": "Article", "publisher": "Fountain City", "year": 2026,
            "url": "https://fountaincity.tech/resources/blog/a-strategic-framework-for-how-to-prioritize-ai-projects/",
            "description": "Statistique clé : jusqu'à 87% des projets d'IA n'atteignent jamais la production, le plus souvent faute de partir d'un vrai problème métier.",
        },
        {
            "id": "src-ai-pilot-design-aiassemblylines", "title": "How Do You Design an AI Pilot That Scales?",
            "type": "Guide", "publisher": "AI Assembly Lines", "year": 2026,
            "url": "https://aiassemblylines.com/post/how-to-design-ai-pilot-that-scales-enterprise-framework",
            "description": "Méthodologie de pilote : population, durée, base de comparaison, seuil d'échec, décision de passage à l'échelle.",
        },
    ],
    "deep-learning": [
        {
            "id": "src-backprop-rumelhart", "title": "Learning representations by back-propagating errors",
            "type": "Article scientifique", "publisher": "Nature (Rumelhart, Hinton, Williams)", "year": 1986,
            "url": "https://www.nature.com/articles/323533a0",
            "description": "L'article fondateur qui a popularisé la rétropropagation comme méthode d'entraînement des réseaux multicouches.",
        },
        {
            "id": "src-cnn-lecun", "title": "Gradient-Based Learning Applied to Document Recognition",
            "type": "Article scientifique", "publisher": "Proceedings of the IEEE (LeCun et al.)", "year": 1998,
            "url": "http://yann.lecun.com/exdb/publis/pdf/lecun-98.pdf",
            "description": "L'article de référence sur LeNet-5, qui établit les principes de convolution et de partage de poids toujours utilisés aujourd'hui.",
        },
        {
            "id": "src-attention-vaswani", "title": "Attention Is All You Need",
            "type": "Article scientifique", "publisher": "arXiv (Vaswani et al.)", "year": 2017,
            "url": "https://arxiv.org/abs/1706.03762",
            "description": "L'article qui introduit l'architecture transformeur et le mécanisme d'attention multi-tête utilisés par la quasi-totalité des modèles de langage actuels.",
        },
        {
            "id": "src-cnn-cs231n", "title": "CS231n: Convolutional Neural Networks for Visual Recognition",
            "type": "Cours", "publisher": "Stanford University", "year": 2026,
            "url": "https://cs231n.github.io/convolutional-networks/",
            "description": "Notes de cours de référence sur les CNN : champ réceptif, partage de poids, calcul des dimensions de sortie.",
        },
    ],
    "software-ai": [
        {
            "id": "src-numpy-vectorization-mlmastery", "title": "7 NumPy Tricks to Vectorize Your Code",
            "type": "Guide", "publisher": "MachineLearningMastery.com", "year": 2026,
            "url": "https://machinelearningmastery.com/7-numpy-tricks-to-vectorize-your-code/",
            "description": "Techniques concrètes de vectorisation NumPy et gains de performance mesurés face aux boucles Python.",
        },
        {
            "id": "src-testing-ml-jeremyjordan", "title": "Effective testing for machine learning systems",
            "type": "Article de référence", "publisher": "Jeremy Jordan", "year": 2026,
            "url": "https://www.jeremyjordan.me/testing-ml/",
            "description": "Panorama des couches de test spécifiques au machine learning : données, invariants du modèle, métriques de référence.",
        },
        {
            "id": "src-fastapi-mlops-pyimagesearch", "title": "FastAPI for MLOps: Python Project Structure and API Best Practices",
            "type": "Guide", "publisher": "PyImageSearch", "year": 2026,
            "url": "https://pyimagesearch.com/2026/04/13/fastapi-for-mlops-python-project-structure-and-api-best-practices/",
            "description": "Bonnes pratiques de contrat d'API, chargement du modèle au démarrage et structuration d'un service FastAPI de scoring.",
        },
        {
            "id": "src-dvc-userguide", "title": "DVC User Guide",
            "type": "Documentation", "publisher": "Data Version Control (DVC)", "year": 2026,
            "url": "https://doc.dvc.org/user-guide",
            "description": "Documentation de référence sur le versionnage des données et la reproductibilité des pipelines ML avec dvc.yaml/dvc.lock.",
        },
    ],
    "cyber-ai": [
        {
            "id": "src-owasp-llm-top10-checkpoint", "title": "Reading the Signals in the OWASP LLM Top 10 2026",
            "type": "Analyse", "publisher": "Check Point Research", "year": 2026,
            "url": "https://blog.checkpoint.com/ai-security/reading-the-signals-in-the-owasp-llm-top-10-2026/amp/",
            "description": "Prompt injection reste en tête du classement OWASP LLM 2026 ; analyse de l'évolution de l'excessive agency et des attaques multimodales.",
        },
        {
            "id": "src-adversarial-ml-taxonomy-nist", "title": "Adversarial Machine Learning: A Taxonomy and Terminology (NIST AI 100-2)",
            "type": "Référentiel", "publisher": "NIST", "year": 2026,
            "url": "https://medium.com/@tahirbalarabe2/%EF%B8%8Fadversarial-machine-learning-a-taxonomy-and-terminology-nist-ai-100-2e2023-fb7ccc11ce98",
            "description": "Taxonomie de référence NIST des attaques adversariales : poisoning, évasion, extraction, inférence d'appartenance.",
        },
        {
            "id": "src-agent-sandbox-northflank", "title": "How to sandbox AI agents in 2026: MicroVMs, gVisor & isolation strategies",
            "type": "Guide", "publisher": "Northflank", "year": 2026,
            "url": "https://northflank.com/blog/how-to-sandbox-ai-agents",
            "description": "Stratégies d'isolation d'agents IA : sandboxing, permissions scindées par capacité, allowlist réseau.",
        },
    ],
    "llm-engineering": [
        {
            "id": "src-bpe-tokenizer-buildfast", "title": "What Is BPE (Byte Pair Encoding)? How Tokenizers Actually Work",
            "type": "Guide", "publisher": "Build Fast with AI", "year": 2026,
            "url": "https://www.buildfastwithai.com/blogs/what-is-bpe-byte-pair-encoding-how-tokenizers-actually-work-2026",
            "description": "Mécanisme de fusion itérative du BPE et arbitrages de taille de vocabulaire (30K à 200K tokens selon les modèles récents).",
        },
        {
            "id": "src-pretraining-curation-spheron", "title": "AI Pretraining Data Curation on GPU Cloud: NeMo Curator, Datatrove, and FineWeb-Style Pipelines",
            "type": "Guide", "publisher": "Spheron Network", "year": 2026,
            "url": "https://www.spheron.network/blog/ai-pretraining-data-curation-nemo-curator-datatrove-fineweb-gpu-cloud/",
            "description": "Étapes du pipeline de curation de corpus de préentraînement : déduplication, filtrage qualité, décontamination des benchmarks.",
        },
        {
            "id": "src-finetuning-lora-dpo-futureagi", "title": "LLM Fine-Tuning Guide 2026: LoRA, QLoRA, DPO, GRPO, RLHF",
            "type": "Guide", "publisher": "FutureAGI", "year": 2026,
            "url": "https://futureagi.com/blog/llm-fine-tuning-guide-2025/",
            "description": "Comparatif des techniques d'adaptation (SFT, LoRA, QLoRA, DPO) et des volumes d'exemples typiques par méthode.",
        },
        {
            "id": "src-llm-judge-openlayer", "title": "LLM-as-judge: A complete guide to evaluation best practices",
            "type": "Guide", "publisher": "Openlayer", "year": 2026,
            "url": "https://www.openlayer.com/blog/llm-as-judge-evaluation-guide",
            "description": "Méthodologie du LLM-as-judge : taux d'accord avec l'évaluation humaine, biais connus et corrections (rotation, étalonnage).",
        },
    ],
    "machine-learning": [
        {
            "id": "src-data-leakage-mlmastery", "title": "3 Subtle Ways Data Leakage Can Ruin Your Models (and How to Prevent It)",
            "type": "Guide", "publisher": "MachineLearningMastery.com", "year": 2026,
            "url": "https://machinelearningmastery.com/3-subtle-ways-data-leakage-can-ruin-your-models-and-how-to-prevent-it/",
            "description": "Formes courantes de fuite de données et méthodes de prévention par découpage temporel et audit de variables.",
        },
        {
            "id": "src-calibration-kdnuggets", "title": "A Deep Dive into Calibration of Language Models: Platt Scaling, Isotonic Regression, Temperature Scaling",
            "type": "Article de référence", "publisher": "KDnuggets", "year": 2026,
            "url": "https://www.kdnuggets.com/a-deep-dive-into-calibration-of-language-models-platt-scaling-isotonic-regression-temperature-scaling",
            "description": "Comparatif des trois méthodes de post-calibration les plus utilisées et de leurs hypothèses respectives.",
        },
        {
            "id": "src-nested-cv-mlmastery", "title": "Nested Cross-Validation for Machine Learning with Python",
            "type": "Guide", "publisher": "MachineLearningMastery.com", "year": 2026,
            "url": "https://machinelearningmastery.com/nested-cross-validation-for-machine-learning-with-python/",
            "description": "Explication du biais d'évaluation optimiste corrigé par la validation croisée imbriquée lors de la sélection d'hyperparamètres.",
        },
        {
            "id": "src-causal-ai-futureagi", "title": "Evaluating Causality in AI Models in 2026: Methods and Tools",
            "type": "Guide", "publisher": "FutureAGI", "year": 2026,
            "url": "https://futureagi.com/blog/evaluating-causality-in-ai-models/",
            "description": "Distinction corrélation/causalité, méthodes d'expérimentation et outils (DoWhy, CausalML) utilisés en production.",
        },
    ],
    "rag-complet": [
        {
            "id": "src-chunking-strategies-firecrawl", "title": "Best Chunking Strategies for RAG (and LLMs) in 2026",
            "type": "Guide", "publisher": "Firecrawl", "year": 2026,
            "url": "https://www.firecrawl.dev/blog/best-chunking-strategies-rag",
            "description": "Comparatif des stratégies de découpage (récursif, sémantique, parent-enfant) avec tailles et taux de recouvrement recommandés.",
        },
        {
            "id": "src-hybrid-search-digitalapplied", "title": "Hybrid Search: BM25, Vector & Reranking Reference 2026",
            "type": "Référentiel technique", "publisher": "Digital Applied", "year": 2026,
            "url": "https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026",
            "description": "Architecture de la recherche hybride, fusion par Reciprocal Rank Fusion, et chiffres de rappel comparés (BM25 seul, vecteur seul, hybride).",
        },
        {
            "id": "src-graphrag-stackviv", "title": "GraphRAG: Knowledge Graphs Meet RAG (2026 Guide)",
            "type": "Guide", "publisher": "StackViv", "year": 2026,
            "url": "https://stackviv.ai/blog/graphrag-knowledge-graphs-rag",
            "description": "Fonctionnement du Graph RAG pour le raisonnement multi-sauts et ses cas d'usage face au RAG vectoriel classique.",
        },
        {
            "id": "src-ragas-metrics-docs", "title": "List of available metrics — Ragas",
            "type": "Documentation", "publisher": "Ragas", "year": 2026,
            "url": "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/",
            "description": "Documentation de référence des métriques RAGAS : faithfulness, answer relevancy, context precision et context recall.",
        },
    ],
    "mathematiques-ia": [
        {
            "id": "src-svd-mlmastery", "title": "Singular Value Decomposition for Dimensionality Reduction in Python",
            "type": "Guide", "publisher": "MachineLearningMastery.com", "year": 2026,
            "url": "https://machinelearningmastery.com/singular-value-decomposition-for-dimensionality-reduction-in-python/",
            "description": "Intuition et mise en œuvre de la SVD pour la réduction de dimensionnalité, base théorique de LoRA.",
        },
        {
            "id": "src-adam-optimizer-geeksforgeeks", "title": "Introduction To Adam Optimizer",
            "type": "Guide", "publisher": "GeeksforGeeks", "year": 2026,
            "url": "https://www.geeksforgeeks.org/deep-learning/adam-optimizer/",
            "description": "Fonctionnement du momentum et de l'adaptation par paramètre dans l'optimiseur Adam, et rôle des schedulers de taux d'apprentissage.",
        },
        {
            "id": "src-perplexity-comet", "title": "Perplexity for LLM Evaluation",
            "type": "Article de référence", "publisher": "Comet", "year": 2026,
            "url": "https://www.comet.com/site/blog/perplexity-for-llm-evaluation/",
            "description": "Définition de la perplexité et limites documentées de sa corrélation avec la performance réelle sur des tâches en aval.",
        },
    ],
    "ai-history": [
        {
            "id": "src-dartmouth-workshop-council", "title": "AI was born at a US summer camp 68 years ago. Here's why that event still matters today",
            "type": "Article historique", "publisher": "International Science Council", "year": 2026,
            "url": "https://council.science/blog/ai-was-born-at-a-us-summer-camp-68-years-ago-heres-why-that-event-still-matters-today/",
            "description": "Récit du séminaire de Dartmouth (1956) où John McCarthy a inventé le terme « intelligence artificielle ».",
        },
    ],
    "agents-ia": [
        {
            "id": "src-agent-idempotence-channel", "title": "How to Build Idempotent Tool Calls for AI Agents",
            "type": "Guide", "publisher": "Chanl", "year": 2026,
            "url": "https://www.channel.tel/blog/idempotent-tool-calls-agent-retry-safety",
            "description": "Conception de contrats d'outils robustes pour agents : clés d'idempotence, gestion des timeouts et des erreurs structurées.",
        },
        {
            "id": "src-multiagent-patterns-digitalapplied", "title": "Multi-Agent Orchestration: 5 Patterns That Work in 2026",
            "type": "Guide", "publisher": "Digital Applied", "year": 2026,
            "url": "https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work",
            "description": "Comparatif des patrons d'orchestration (superviseur, pipeline, débat, fan-out, swarm) et de leur coût en tokens.",
        },
        {
            "id": "src-agent-eval-confidentai", "title": "LLM Agent Evaluation Metrics in 2026: Tool Calling, Task Completion, Reasoning, and Trace-Based Evals",
            "type": "Guide", "publisher": "Confident AI", "year": 2026,
            "url": "https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide",
            "description": "Méthodologie d'évaluation par trajectoire complète (pas seulement le résultat final) : justesse des outils, récupération d'erreur, transfert humain.",
        },
        {
            "id": "src-alexnet-imagenet-pinecone", "title": "AlexNet and ImageNet: The Birth of Deep Learning",
            "type": "Article historique", "publisher": "Pinecone", "year": 2026,
            "url": "https://www.pinecone.io/learn/series/image-search/imagenet/",
            "description": "Récit de la victoire d'AlexNet au concours ImageNet 2012, convergence de trois facteurs (algorithmes, GPU, données annotées) qui a lancé le deep learning.",
        },
        {
            "id": "src-alphago-zero-deepmind", "title": "Mastering the game of Go without human knowledge",
            "type": "Article scientifique", "publisher": "Nature (Silver et al., DeepMind)", "year": 2017,
            "url": "https://www.nature.com/articles/nature24270",
            "description": "Article original décrivant AlphaGo Zero, qui a appris uniquement par auto-apprentissage sans données de parties humaines.",
        },
    ],
    "donnees-architecture": [
        {
            "id": "src-row-vs-column-clickhouse", "title": "Row-oriented vs column-oriented databases: a head-to-head comparison",
            "type": "Référentiel technique", "publisher": "ClickHouse", "year": 2026,
            "url": "https://clickhouse.com/resources/engineering/row-vs-column-database",
            "description": "Comparatif chiffré des performances ligne vs colonne selon le type de requête (recherche ponctuelle vs agrégation large).",
        },
        {
            "id": "src-lakehouse-formats-amdatalakehouse", "title": "Lakehouse Table Formats in 2026: Iceberg, Delta Lake, Hudi, Paimon, and DuckLake",
            "type": "Guide", "publisher": "AM Data Lakehouse", "year": 2026,
            "url": "https://amdatalakehouse.substack.com/p/lakehouse-table-formats-in-2026-iceberg",
            "description": "État des lieux des formats de table ouverts (Iceberg, Delta Lake, Hudi) et de leurs garanties transactionnelles.",
        },
        {
            "id": "src-cap-theorem-algomaster", "title": "CAP Theorem Explained",
            "type": "Article de référence", "publisher": "AlgoMaster", "year": 2026,
            "url": "https://blog.algomaster.io/p/cap-theorem-explained",
            "description": "Formalisation du théorème CAP et de l'arbitrage cohérence/disponibilité en cas de partition réseau.",
        },
        {
            "id": "src-raft-yugabyte", "title": "Raft Protocol: What is the Raft Consensus Algorithm?",
            "type": "Référentiel technique", "publisher": "YugabyteDB", "year": 2026,
            "url": "https://www.yugabyte.com/key-concepts/raft-consensus-algorithm/",
            "description": "Mécanisme d'élection de leader et de validation par quorum de l'algorithme de consensus Raft.",
        },
    ],
    "gouvernance-ia": [
        {
            "id": "src-eu-ai-act-tiers-jaggaer", "title": "EU AI Act Risk Categories: The 4 Tiers Explained",
            "type": "Guide", "publisher": "Jaggaer", "year": 2026,
            "url": "https://www.jaggaer.com/blog/eu-ai-act-risk-categories",
            "description": "Les quatre paliers de risque de l'EU AI Act et leur calendrier d'entrée en application jusqu'en 2026.",
        },
        {
            "id": "src-nist-ai-rmf-balancedsec", "title": "NIST AI RMF: Govern, Map, Measure, Manage Explained",
            "type": "Guide", "publisher": "Balanced Security", "year": 2026,
            "url": "https://blog.balancedsec.com/p/original-inside-the-nist-ai-risk",
            "description": "Explication des quatre fonctions du NIST AI Risk Management Framework et de leur articulation.",
        },
        {
            "id": "src-china-ai-governance-gaeedu", "title": "China AI Governance Profile 2026: Regulation, Policy & Workforce Implications",
            "type": "Analyse", "publisher": "GAEEDU", "year": 2026,
            "url": "https://gaeedu.org/ai-governance-profiles/china",
            "description": "Panorama de l'architecture réglementaire chinoise par empilement de textes sectoriels et de l'initiative IA+.",
        },
        {
            "id": "src-iso-42001-openlayer", "title": "ISO 42001: A Complete Guide to AI Management Systems",
            "type": "Guide", "publisher": "Openlayer", "year": 2026,
            "url": "https://www.openlayer.com/blog/iso-42001-ai-management-systems-guide",
            "description": "Structure du système de management ISO/IEC 42001 (PDCA), exigences d'évaluation d'impact et intégration avec ISO 27001.",
        },
    ],
    "infrastructure-mlops": [
        {
            "id": "src-llm-vram-spheron", "title": "LLM VRAM Requirements: How Much GPU Memory You Need",
            "type": "Guide", "publisher": "Spheron Network", "year": 2026,
            "url": "https://www.spheron.network/blog/gpu-memory-requirements-llm/",
            "description": "Répartition détaillée de la mémoire GPU (poids, gradients, états optimiseur, activations) avec ordres de grandeur chiffrés.",
        },
        {
            "id": "src-llm-serving-spheron", "title": "LLM Serving Optimization: Continuous Batching, PagedAttention, and Chunked Prefill on H100",
            "type": "Guide", "publisher": "Spheron Network", "year": 2026,
            "url": "https://www.spheron.network/blog/llm-serving-optimization-continuous-batching-paged-attention/",
            "description": "Mécanique du batching continu et de PagedAttention, avec les gains d'efficacité mémoire mesurés en production.",
        },
        {
            "id": "src-llm-quantization-tensorfoundry", "title": "LLM Quantisation: A Field Guide",
            "type": "Guide", "publisher": "TensorFoundry", "year": 2026,
            "url": "https://tensorfoundry.io/blog/llm-quantisation-field-guide",
            "description": "Comparatif PTQ/QAT selon le niveau de précision visé et techniques de gestion des valeurs aberrantes d'activation.",
        },
        {
            "id": "src-llm-routing-digitalapplied", "title": "LLM Model Routing in 2026: Cost-Quality Optimization",
            "type": "Guide", "publisher": "Digital Applied", "year": 2026,
            "url": "https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide",
            "description": "Stratégies de routage et de cascade de modèles pour réduire le coût d'inférence sans dégrader la qualité perçue.",
        },
    ],
}


def seed_course_bibliographies(db: Session) -> None:
    total = 0
    for course_id, sources in _COURSE_BIBLIOGRAPHIES.items():
        for r in sources:
            resource = _get_or_create(
                db, Resource, r["id"],
                title=r["title"], type=r.get("type"), url=r.get("url"), publisher=r.get("publisher"),
                year=r.get("year"), description=r.get("description"), status=ContentStatus.PUBLISHED,
            )
            db.flush()
            exists = db.execute(
                resource_courses.select().where(
                    resource_courses.c.resource_id == resource.id, resource_courses.c.course_id == course_id
                )
            ).first()
            if not exists:
                db.execute(resource_courses.insert().values(resource_id=resource.id, course_id=course_id))
            total += 1
    db.flush()
    print(f"  course_bibliographies: {total} sources sur {len(_COURSE_BIBLIOGRAPHIES)} cours")


def seed_interactive_labs(db: Session) -> None:
    """Labs au format « schéma interactif » — contenu original, pas dérivé du
    prototype. Refonte progressive de la section Labs (cf. discussion de
    conception) : chaque lab de cette liste porte un schéma cliquable
    (InteractiveStepPipeline côté frontend) en plus de son contenu texte."""
    for spec in _INTERACTIVE_LABS:
        lab = _get_or_create(
            db, Lab, spec["id"],
            school_id=spec["school_id"], lesson_id=None,
            title=spec["title"], level=spec["level"], duration_min=spec["duration_min"],
            color=spec["color"], description=spec["description"],
            environment="Aucun environnement technique requis — exploration guidée du schéma interactif.",
            instructions=spec["instructions"], deliverable=spec["deliverable"],
            evaluation_note=spec["evaluation_note"], interactive_steps=spec["steps"],
            status=ContentStatus.PUBLISHED,
        )
        db.flush()

        for skill_id in spec["skills"]:
            exists = db.execute(
                lab_skills.select().where(lab_skills.c.lab_id == lab.id, lab_skills.c.skill_id == skill_id)
            ).first()
            if not exists:
                db.execute(lab_skills.insert().values(lab_id=lab.id, skill_id=skill_id))

        for mode in ("Guidé", "Exploration"):
            exists = db.execute(
                lab_modes.select().where(lab_modes.c.lab_id == lab.id, lab_modes.c.mode == mode)
            ).first()
            if not exists:
                db.execute(lab_modes.insert().values(lab_id=lab.id, mode=mode))

    db.flush()
    print(f"  interactive_labs: {len(_INTERACTIVE_LABS)}")


def seed_questions(db: Session, data: dict) -> None:
    for qb in data["questionBanks"]:
        _get_or_create(db, QuestionBank, qb["id"], title=qb["title"], description=qb.get("description"))
    db.flush()

    for q in data["questions"]:
        question = _get_or_create(
            db, Question, q["id"],
            skill_id=q.get("skillId"), domain=q.get("domain"), difficulty=q.get("difficulty", 1),
            question_text=q["question"], explanation=q.get("explanation"),
            status=ContentStatus.PUBLISHED,
        )
        db.flush()
        db.query(QuestionOption).filter(QuestionOption.question_id == question.id).delete()
        correct_index = q.get("correct")
        for pos, option_text in enumerate(q.get("options", [])):
            db.add(QuestionOption(
                question_id=question.id, position=pos, option_text=option_text,
                is_correct=(pos == correct_index),
            ))
    db.flush()
    print(f"  question_banks: {len(data['questionBanks'])}, questions: {len(data['questions'])}")


MAX_QUESTIONS_PER_PRACTICE_QUIZ = 10


def seed_practice_quizzes(db: Session, data: dict) -> None:
    """Assemble un quiz d'entraînement (PRACTICE) par compétence, à partir
    des questions déjà seedées. Aucune interface d'administration ne permet
    encore de composer des quiz manuellement (viendra avec le CMS) — cette
    génération automatique est un pont pragmatique pour disposer de quiz
    réels et testables dès maintenant. Idempotent : recherche un quiz
    PRACTICE existant pour la compétence avant d'en créer un nouveau."""
    skill_ids = sorted({q["skillId"] for q in data["questions"] if q.get("skillId")})

    created_or_updated = 0
    for skill_id in skill_ids:
        skill = db.get(Skill, skill_id)
        if skill is None:
            continue  # ne devrait pas arriver (intégrité déjà vérifiée), sécurité seulement

        quiz = (
            db.query(Quiz)
            .filter(Quiz.skill_id == skill_id, Quiz.kind == QuizKind.PRACTICE)
            .first()
        )
        if quiz is None:
            quiz = Quiz(
                title=f"Quiz de pratique — {skill.name}",
                kind=QuizKind.PRACTICE,
                skill_id=skill_id,
                pass_threshold=70,
                status=ContentStatus.PUBLISHED,
            )
            db.add(quiz)
            db.flush()  # obtient quiz.id (UUID généré côté serveur)

        question_ids = [
            q.id for q in db.query(Question.id)
            .filter(Question.skill_id == skill_id)
            .order_by(Question.id)
            .limit(MAX_QUESTIONS_PER_PRACTICE_QUIZ)
        ]
        db.execute(quiz_questions.delete().where(quiz_questions.c.quiz_id == quiz.id))
        for pos, qid in enumerate(question_ids):
            db.execute(quiz_questions.insert().values(quiz_id=quiz.id, question_id=qid, position=pos))
        created_or_updated += 1

    db.flush()
    print(f"  quizzes (practice, un par compétence): {created_or_updated}")


def seed_resources_and_glossary(db: Session, data: dict) -> None:
    for r in data["resources"]:
        resource = _get_or_create(
            db, Resource, r["id"],
            title=r["title"], type=r.get("type"), publisher=r.get("publisher"), year=r.get("year"),
            level=r.get("level"), description=r.get("description"), status=ContentStatus.PUBLISHED,
        )
        db.flush()
        for tag in r.get("tags", []):
            exists = db.execute(
                resource_tags.select().where(resource_tags.c.resource_id == resource.id, resource_tags.c.tag == tag)
            ).first()
            if not exists:
                db.execute(resource_tags.insert().values(resource_id=resource.id, tag=tag))
    db.flush()

    for g in data["glossary"]:
        existing = db.query(GlossaryTerm).filter(GlossaryTerm.term == g["term"]).first()
        if existing is None:
            db.add(GlossaryTerm(
                term=g["term"], term_en=g.get("en"), definition=g["definition"],
                status=ContentStatus.PUBLISHED,
            ))
        else:
            existing.term_en = g.get("en")
            existing.definition = g["definition"]
    db.flush()
    print(f"  resources: {len(data['resources'])}, glossary_terms: {len(data['glossary'])}")


def seed_governance(db: Session, data: dict) -> None:
    frameworks = data.get("frameworks", {})
    for iso in frameworks.get("iso", []):
        _get_or_create(db, GovernanceStandard, iso["id"], name=iso["name"], purpose=iso.get("purpose"))
    for j in frameworks.get("jurisdictions", []):
        _get_or_create(db, GovernanceJurisdiction, j["id"], name=j["name"], focus=j.get("focus"))
    db.flush()
    print(f"  governance_standards: {len(frameworks.get('iso', []))}, "
          f"governance_jurisdictions: {len(frameworks.get('jurisdictions', []))}")


def seed_knowledge_graph(db: Session, data: dict) -> None:
    for k in data["knowledgeGraph"]:
        node = _get_or_create(
            db, KnowledgeNode, k["id"],
            title=k["title"], stage=k.get("stage"), formula=k.get("formula"),
            guiding_question=k.get("question"), status=ContentStatus.PUBLISHED,
        )
        db.flush()

        db.query(KnowledgeNodeApplication).filter(KnowledgeNodeApplication.node_id == node.id).delete()
        for label in k.get("applications", []):
            db.add(KnowledgeNodeApplication(node_id=node.id, label=label))

    db.flush()

    # associations (nécessitent que tous les nœuds existent déjà)
    for k in data["knowledgeGraph"]:
        for dep_id in k.get("dependsOn", []):
            exists = db.execute(
                knowledge_node_dependencies.select().where(
                    knowledge_node_dependencies.c.node_id == k["id"],
                    knowledge_node_dependencies.c.depends_on_node_id == dep_id,
                )
            ).first()
            if not exists:
                db.execute(knowledge_node_dependencies.insert().values(node_id=k["id"], depends_on_node_id=dep_id))

        # "usedIn" pointe vers des leçons, pas d'autres nœuds (vérifié sur les données réelles).
        # Une leçon du prototype peut avoir été fusionnée/supprimée depuis (cf.
        # _MERGED_AWAY_LESSON_IDS) : on l'ignore silencieusement plutôt que de
        # planter sur une clé étrangère vers une leçon qui n'existe plus.
        for lesson_id in k.get("usedIn", []):
            if db.get(Lesson, lesson_id) is None:
                continue
            exists = db.execute(
                knowledge_node_used_in_lessons.select().where(
                    knowledge_node_used_in_lessons.c.node_id == k["id"],
                    knowledge_node_used_in_lessons.c.lesson_id == lesson_id,
                )
            ).first()
            if not exists:
                db.execute(knowledge_node_used_in_lessons.insert().values(node_id=k["id"], lesson_id=lesson_id))

        for demo_id in k.get("demos", []):
            exists = db.execute(
                knowledge_node_demos.select().where(
                    knowledge_node_demos.c.node_id == k["id"], knowledge_node_demos.c.demo_id == demo_id
                )
            ).first()
            if not exists:
                db.execute(knowledge_node_demos.insert().values(node_id=k["id"], demo_id=demo_id))

        for lab_id in k.get("labs", []):
            exists = db.execute(
                knowledge_node_labs.select().where(
                    knowledge_node_labs.c.node_id == k["id"], knowledge_node_labs.c.lab_id == lab_id
                )
            ).first()
            if not exists:
                db.execute(knowledge_node_labs.insert().values(node_id=k["id"], lab_id=lab_id))
    db.flush()
    print(f"  knowledge_nodes: {len(data['knowledgeGraph'])}")


_PERCENT_RE = re.compile(r"(\d+)\s*%")


def _infer_requirement(text: str) -> tuple[CertificationRequirementType, int | None]:
    """Heuristique de conversion des critères texte libre du prototype
    (ex: 'Quiz ≥ 75 %') vers le type structuré du schéma. Résultat approximatif,
    à affiner manuellement depuis l'admin une fois le CMS disponible."""
    m = _PERCENT_RE.search(text)
    if m:
        return CertificationRequirementType.MIN_SCORE, int(m.group(1))
    return CertificationRequirementType.EVIDENCE, None


def seed_certifications(db: Session, data: dict) -> None:
    for c in data["certifications"]:
        cert = _get_or_create(
            db, Certification, c["id"],
            title=c["title"], level=c.get("level"), description=c.get("description"),
            color=c.get("color"), legacy_threshold=c.get("threshold"), status=ContentStatus.PUBLISHED,
        )
        db.flush()
        db.query(CertificationRequirement).filter(CertificationRequirement.certification_id == cert.id).delete()
        for pos, req_text in enumerate(c.get("requirements", [])):
            req_type, min_score = _infer_requirement(req_text)
            db.add(CertificationRequirement(
                certification_id=cert.id, requirement_type=req_type,
                min_score=min_score, description=req_text, position=pos,
            ))
    db.flush()
    print(f"  certifications: {len(data['certifications'])}")


def run() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} introuvable. Exportez d'abord CASA_DATA depuis le "
            "prototype HTML vers ce fichier JSON."
        )
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        print("Seed en cours...")
        seed_schools(db, data)
        seed_skills(db, data)
        seed_profile_types_and_goals(db, data)
        seed_demos(db, data)
        seed_pathways_and_courses(db, data)
        seed_lessons(db, data)
        seed_labs(db, data)
        seed_interactive_labs(db)
        seed_questions(db, data)
        seed_practice_quizzes(db, data)
        seed_resources_and_glossary(db, data)
        seed_course_bibliographies(db)
        seed_governance(db, data)
        seed_knowledge_graph(db, data)
        seed_certifications(db, data)
        db.commit()
        print("Seed terminé avec succès.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
