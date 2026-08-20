# DATABASE_AUDIT.md — Phase 0

**Statut : audit seul. Aucun fichier de code, modèle, migration ou donnée n'a été modifié pour produire ce rapport.**

Date : 2026-08-19
Méthode : lecture directe du code (backend, migrations, seed), inspection de la base PostgreSQL réellement en cours d'exécution (`docker compose exec postgres psql`), et des données seedées.

---

## 1. Architecture actuelle

```
casa-project/
├── db/
│   ├── schema.sql                 # schéma de référence (dump SQL manuel, PAS généré par Alembic)
│   └── provision_extensions.sql   # pgcrypto, citext, vector — exécuté une fois par un superuser
├── backend/
│   ├── app/
│   │   ├── models/        # SQLAlchemy 2.0 (Mapped[...]), 12 modules, mirror de schema.sql
│   │   ├── api/            # 13 routers FastAPI
│   │   ├── repositories/   # accès données, un repo par domaine
│   │   ├── services/       # logique métier
│   │   ├── schemas/        # Pydantic v2 (I/O API)
│   │   ├── core/           # config (pydantic-settings), sécurité (JWT, bcrypt)
│   │   └── db/session.py
│   ├── migrations/versions/   # Alembic, 5 révisions (0001→0005)
│   ├── scripts/seed.py        # charge backend/data/casa_data.json en base
│   └── data/casa_data.json    # export du prototype HTML (473 Ko, 17 clés racine)
└── frontend/               # React/TS/Vite — hors périmètre Phase 0
```

**Stack** : FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16 (image `pgvector/pgvector:pg16`) + Redis (provisionné, non utilisé par le code actuel — aucun `import redis` trouvé) + JWT (PyJWT/bcrypt).

**Alembic** : `migrations/env.py` pointe `target_metadata = Base.metadata` (import de `app.models`, qui importe tous les sous-modules) et `compare_type=True`. L'autogenerate est donc fiable pour la Phase 1 — pas besoin d'écrire les migrations entièrement à la main.

**⚠️ Pas de dépôt Git.** `git status` échoue (`fatal: not a git repository`). Il n'existe donc **aucun filet de sécurité** (rollback, diff, historique) pour les phases à venir. C'est un risque de premier ordre pour une mission qui modifie un schéma de production, avant même de parler de RAG — voir §6.

**Pas de suite de tests.** Aucun fichier `test_*.py` / `*_test.py` dans tout le dépôt. Le README revendique des tests manuels "en installation native" mais rien n'est automatisé ni rejouable.

---

## 2. Schéma actuel — 56 tables

`db/schema.sql` (664 lignes, SQL brut à jour jusqu'à la migration 0004) sert de documentation de référence, mais **a divergé de la réalité** : la migration `0005_add_course_certificates` (ajoutée dans cette session, hors mission RAG) n'y est pas reportée. `schema.sql` n'est pas généré automatiquement — c'est un fichier maintenu à la main, en parallèle des migrations Alembic qui sont la vraie source de vérité en base. À corriger avant ou pendant la Phase 1 pour ne pas partir d'une carte fausse.

Tables par domaine :

| Domaine | Tables |
|---|---|
| Utilisateurs / auth | `users`, `learner_profile_types`, `goals`, `user_profiles`, `user_profile_goals`, `user_profile_interest_skills` |
| Référentiel pédagogique | `schools`, `skills`, `pathways`, `pathway_prerequisites`, `pathway_skills`, `courses`, `course_prerequisites`, `course_skills`, `pathway_courses`, `demos` |
| Contenu de leçon | `lessons`, `lesson_objectives`, `lesson_sections`, `lesson_depth_levels` |
| Labs | `labs`, `lab_skills`, `lab_modes` |
| Quiz | `question_banks`, `questions`, `question_options`, `quizzes`, `quiz_questions` |
| Ressources | `resources`, `resource_tags`, `resource_courses`, `resource_lessons`, `resource_skills`, `glossary_terms`, `governance_standards`, `governance_jurisdictions` |
| Knowledge Graph | `knowledge_nodes`, `knowledge_node_dependencies`, `knowledge_node_used_in_lessons`, `knowledge_node_applications`, `knowledge_node_demos`, `knowledge_node_labs` |
| Certifications | `certifications`, `certification_requirements`, `user_certifications` |
| Progression | `user_lesson_progress`, `user_skills`, `quiz_attempts`, `quiz_attempt_answers`, `lab_results`, `portfolio_evidence`, `portfolio_evidence_skills`, `demo_views` |
| Notifications / IA | `notifications`, `ai_conversations`, `ai_messages` |
| *(hors schema.sql)* | `course_certificates` — migration 0005, session courante |

**Total réel actuel : 57 tables** (56 + `course_certificates`).

### Enums PostgreSQL (9)

`user_role`, `account_status`, `content_status` (DRAFT/PUBLISHED/ARCHIVED — utilisé partout comme statut éditorial), `lesson_depth_key` (ESSENTIAL/TECHNICAL/MATHEMATICS/IMPLEMENTATION/ARCHITECTURE/GOVERNANCE), `quiz_kind` (PRACTICE/VALIDATION/FINAL), `certification_requirement_type`, `user_certification_status`, `lesson_progress_status`, `notification_type`, `ai_message_role`.

**Point important pour la Phase 1 (§12 de la mission)** : il n'existe **aucun enum `source_type` ou équivalent** aujourd'hui. Le nouvel enum RAG sera donc entièrement nouveau — pas de risque de doublon, mais il faut nommer ses valeurs pour qu'elles correspondent 1:1 aux tables/entités réellement traçables (voir §7).

### Index explicites : seulement 10

```
idx_lessons_course_id, idx_lessons_status, idx_courses_school_id,
idx_user_lesson_progress_user, idx_quiz_attempts_user, idx_lab_results_user,
idx_notifications_user_unread (partiel), idx_ai_messages_conversation,
idx_portfolio_evidence_user, idx_questions_skill_id
```

PostgreSQL indexe automatiquement les clés primaires, **pas les clés étrangères**. Plusieurs FK à forte cardinalité de requêtes ne sont pas indexées, notamment `quizzes.course_id`, `quizzes.lesson_id`, `quizzes.skill_id` (utilisées par le filtre `list_course_quizzes` ajouté cette session) et `lesson_sections.lesson_id`. À surveiller pour les colonnes `chunks.course_id/lesson_id/section_id` de la Phase 1 — la mission le demande explicitement (§30), et l'état actuel montre que ce n'est pas un réflexe déjà pris dans ce projet.

### Contraintes

Peu nombreuses et ciblées : anti-auto-référence (`pathway_prerequisites`, `course_prerequisites`, `knowledge_node_dependencies` interdisent qu'une ligne se référence elle-même), `UNIQUE` sur `users.email`, `glossary_terms.term`, `(lesson_id, depth_key)`, `(user_id, certification_id)`, `(user_id, course_id)` (nouvelle, `course_certificates`). Aucune contrainte `CHECK` de validation de contenu (longueur, format).

---

## 3. Modèle pédagogique (à préserver — §8 de la mission)

```
School (13) ──< Skill (41)
   │
   └─< Course (26) ──< Lesson (95) ──┬─< LessonSection (slides)
                                       ├─< LessonObjective
                                       └─< LessonDepthLevel (0–6 par leçon, clé = lesson_depth_key)

Pathway (11) >──< Course   (via pathway_courses, M:N ordonné par position)
```

Confirmé en base (comptes réels après seed) :

| Table | Lignes |
|---|---|
| schools | 13 |
| skills | 41 |
| pathways | 11 |
| courses | 26 |
| lessons | 95 |
| labs | 10 |
| resources | 22 |
| glossary_terms | 24 |
| knowledge_nodes | 16 |
| questions | 326 |
| quizzes | 23 (**100% de kind = PRACTICE** — voir §5) |
| certifications | 4 |
| demos | 60 |

`Course` n'a **pas** de colonne `pathway_id` directe : le rattachement passe uniquement par la table d'association `pathway_courses` (un cours peut apparaître dans plusieurs parcours). Un cours n'a pas non plus de FK `skill_id` unique — la relation compétences↔cours passe par `course_skills` (M:N) **et** indirectement par `lesson.skill_id` (1 compétence par leçon, nullable). Les deux mécanismes coexistent et ne sont pas garantis cohérents entre eux (rien n'empêche `course_skills` de lister une compétence qu'aucune leçon du cours n'enseigne). À garder en tête pour le Document Builder (Phase 3) : la provenance "quelles compétences couvre ce contenu" doit être dérivée soigneusement, pas supposée.

`LessonSection` (le "slide" au sens de la mission, §14) a aujourd'hui : `id, lesson_id, position, title, body, image_url, image_alt`. **Aucun `section_type`, `summary`, `language` ou `metadata`** — confirme qu'il faudra bien les ajouter en Phase 2, rien d'équivalent n'existe sous un autre nom.

---

## 4. pgvector et Knowledge Graph : provisionnés mais inertes

Deux constats structurants pour la suite, vérifiés dans le code et en base :

### pgvector

`CREATE EXTENSION IF NOT EXISTS vector` est bien exécuté (`db/provision_extensions.sql`, commentaire du schema.sql : *"pgvector, pour le RAG (V6) — sans impact ici, préparé à l'avance"*). Mais :
- **Aucune colonne de type `vector` n'existe dans aucune table.**
- **Aucun modèle SQLAlchemy n'importe `pgvector.sqlalchemy`** (`grep -R vector backend/app/models` : zéro résultat).
- **Aucune dépendance `pgvector` dans `requirements.txt`** — il faudra l'ajouter (`pip install pgvector`) avant la Phase 1.

Conclusion : l'extension est prête côté PostgreSQL, mais toute la couche `documents/chunks/embeddings` est à construire depuis zéro, sans rien à migrer ou à concilier.

### Knowledge Graph

`knowledge_nodes` et ses tables de liaison existent, sont **seedées (16 nœuds)**, mais :
- **Aucun repository** (`grep` sur `backend/app/repositories` : rien pour `knowledge`).
- **Aucune route API** (`/api/knowledge*` n'existe pas).
- **Aucune référence dans le frontend** (`grep -i knowledge frontend/src` : rien).

Le Knowledge Graph mentionné dans la mission comme "existant" à préserver est donc **des données dormantes, jamais exposées ni consommées par l'application**. C'est une bonne nouvelle pour le risque (rien ne peut casser en le touchant, aucun utilisateur ne dépend de son comportement actuel) mais une donnée factuelle importante à ne pas survendre dans le plan : il n'y a pas de "graphe vivant" à intégrer, juste des tables de données à activer.

Le même constat s'applique, dans une moindre mesure, à `resources`, `glossary_terms`, `governance_standards`/`governance_jurisdictions` et `demos` : **seedés mais sans aucune route API ni usage frontend**. Ce sont pourtant précisément des candidats `source_type` de premier choix pour le RAG (contenu court, dense, déjà structuré) — les activer pour le RAG sera la première fois qu'ils deviennent utiles à un utilisateur final.

---

## 5. Système de quiz — écart entre modèle et données réelles

Le modèle `Quiz` prévoit 3 natures (`quiz_kind` : PRACTICE / VALIDATION / FINAL) et peut être rattaché à `course_id`, `lesson_id` ou `skill_id`. **En pratique, `scripts/seed.py` ne génère que des quiz PRACTICE, rattachés à une compétence (`skill_id`)** — confirmé par requête SQL directe (`select kind, count(*) from quizzes group by kind` → `PRACTICE | 23`, aucune autre ligne).

Conséquence déjà rencontrée cette session (fonctionnalité "certificat de module") : la notion de "quiz d'un cours" n'est pas portée par une colonne directe fiable — elle doit être dérivée en remontant `Lesson.skill_id → Quiz.skill_id`. Ce sera pertinent pour `chunk_type`/provenance en Phase 1 : ne pas supposer que `quizzes.course_id`/`quizzes.lesson_id` sont peuplés dans les données réelles actuelles, même si le modèle les permet.

---

## 6. Risques

| # | Risque | Sévérité | Détail |
|---|---|---|---|
| R1 | **Pas de Git** | Élevée | Aucun rollback possible autrement qu'en restaurant un dump PostgreSQL. Toute migration de schéma ratée est difficile à annuler proprement. **Recommandation : initialiser un dépôt Git et committer l'état actuel avant toute Phase 1**, indépendamment du reste. |
| R2 | **Pas de tests automatisés** | Élevée | §27 de la mission demande des tests de non-régression (comparer les volumes avant/après). Sans suite existante, ces tests devront être écrits de zéro dès la Phase 1, pas juste complétés. |
| R3 | **`schema.sql` désynchronisé** | Faible | Un contributeur qui lit `schema.sql` comme référence manquera `course_certificates`. À corriger (ou à documenter comme non-fiable, Alembic faisant foi). |
| R4 | **Indexation FK incomplète** | Moyenne | Filtrage par `course_id`/`lesson_id`/`skill_id` déjà utilisé sans index dédié (ex. `quizzes`). Le futur `chunks` devra explicitement indexer ces colonnes dès sa création, ne pas compter sur un réflexe déjà en place dans le projet. |
| R5 | **Ambiguïté cours↔compétence** | Moyenne | Deux chemins non garantis cohérents (`course_skills` direct vs `lesson.skill_id` agrégé) pour savoir "quelles compétences couvre ce cours". Le Document Builder (Phase 3) doit choisir une source unique et la documenter, sous peine de métadonnées de provenance incohérentes selon le chemin de calcul utilisé. |
| R6 | **`redis` provisionné, non utilisé** | Faible | Le service tourne dans `docker-compose.yml` mais rien dans le code ne l'utilise. Non bloquant pour le RAG, mais à clarifier si une future queue de génération d'embeddings (Phase 10) doit s'appuyer dessus. |
| R7 | **PDF import très primitif** | Faible | `pdf_import_service.py` fait un `extract_text()` brut, une section = une page brute, sans détection de titres ni découpage sémantique (assumé explicitement dans le docstring du fichier). Le futur `chunking_service.py` (Phase 4) ne pourra pas réutiliser cette sortie telle quelle comme un chunking "au sens" — c'est un import de contenu, pas un chunker. |
| R8 | **`environment: development` par défaut** | Faible | `docker-compose.yml` : `DEBUG=true`, CORS ouvert sur `localhost:5173` uniquement en dev — sans lien direct avec le RAG, mais à garder à l'esprit si Phase 1+ introduit des endpoints d'administration des embeddings. |

Aucun risque de **perte de données existantes** identifié dans le plan RAG lui-même : toutes les tables citées dans la mission (§34, liste des interdits) sont additives par construction (`documents`, `chunks`, `embeddings` sont de nouvelles tables ; rien dans le plan ne demande de modifier une colonne existante des tables pédagogiques, hormis l'enrichissement additif de `lesson_sections` en Phase 2).

---

## 7. Proposition de schéma cible (pour validation avant Phase 1 — non implémenté)

Reprend fidèlement la structure demandée en §10 de la mission, ajustée aux noms de tables réels de ce projet :

```
documents
----------------------------
id              UUID PK
source_type     source_type_enum NOT NULL   -- COURSE|LESSON|SECTION|DEPTH_LEVEL|RESOURCE|LAB|DEMO|GLOSSARY|KNOWLEDGE_NODE
source_id       TEXT NOT NULL               -- id de la ligne d'origine (type variable : lessons.id est TEXT, pas UUID)
title           TEXT NOT NULL
content         TEXT NOT NULL               -- texte normalisé, assemblé par document_service.py
summary         TEXT
language         TEXT NOT NULL DEFAULT 'fr'
version         INTEGER NOT NULL DEFAULT 1
status          content_status_enum         -- réutilise l'enum existant (DRAFT/PUBLISHED/ARCHIVED) plutôt que d'en recréer un
content_hash    TEXT NOT NULL               -- sha256(content), pour la régénération incrémentale §23
metadata        JSONB
created_at, updated_at

UNIQUE (source_type, source_id)   -- un document par entité source, régénéré en place

chunks
----------------------------
id              UUID PK
document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE
chunk_index     INTEGER NOT NULL
content         TEXT NOT NULL
token_count     INTEGER
chunk_type      TEXT                        -- ex: valeurs alignées sur le futur lesson_sections.section_type (Phase 2)
course_id       TEXT REFERENCES courses(id) ON DELETE CASCADE      -- dénormalisé depuis document_id pour un filtrage direct (§17)
lesson_id       TEXT REFERENCES lessons(id) ON DELETE CASCADE
section_id      UUID REFERENCES lesson_sections(id) ON DELETE CASCADE
language        TEXT NOT NULL DEFAULT 'fr'
level           TEXT                        -- N1..N4, recopié depuis course/lesson
depth           lesson_depth_key_enum        -- réutilise l'enum existant, ne PAS en recréer un
metadata        JSONB
created_at, updated_at

embeddings
----------------------------
id              UUID PK
chunk_id        UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE
model           TEXT NOT NULL
dimension       INTEGER NOT NULL
embedding       vector(dimension)           -- dimension exacte du modèle configuré, jamais codée en dur (§21/§30)
created_at

UNIQUE (chunk_id, model)   -- un embedding par (chunk, modèle) — permet la coexistence de plusieurs modèles, §22

-- association tables, créées seulement si le besoin est confirmé en Phase 5/6 :
chunk_skills            (chunk_id, skill_id)
chunk_knowledge_nodes    (chunk_id, knowledge_node_id)
```

Points d'attention identifiés par cet audit, à trancher explicitement en Phase 1 (pas de décision prise ici) :
1. **Types d'ID hétérogènes** : la plupart des tables pédagogiques utilisent des clés primaires `String` lisibles (`"agents-panorama"`), pas des UUID. `documents.source_id` doit donc être `TEXT`, pas `UUID`, pour pouvoir référencer indifféremment `courses.id`, `lessons.id` (TEXT) ou `resources.id` (TEXT).
2. **`chunks.course_id`/`lesson_id`/`section_id` dénormalisés** : la mission les demande explicitement au niveau du chunk (§17) plutôt que de forcer un `JOIN` via `documents` à chaque requête de retrieval — cohérent avec la nécessité de filtrage rapide en Phase RAG (metadata search de l'architecture cible §3 de la mission).
3. **Réutiliser `content_status` et `lesson_depth_key`** plutôt que recréer des enums équivalents (règle §12 : *"avant de créer un nouvel enum, vérifier les conventions déjà présentes"*).
4. **Dimension du vecteur** : à fixer une fois le modèle d'embedding choisi (§30 — *"ne pas inventer la dimension"*) ; aucun modèle n'est actuellement configuré nulle part dans le projet (`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` n'existent pas encore dans `core/config.py`).

---

## 8. Plan de migration proposé (haut niveau — phases de la mission, non commencées)

| Phase | Contenu | Dépend de |
|---|---|---|
| 1 | Migration Alembic : tables `documents`, `chunks`, `embeddings` (+ index `chunks(course_id/lesson_id/section_id/level/depth)`, `documents(source_type, source_id)`) | Validation de ce rapport + choix du modèle d'embedding (dimension) |
| 2 | Migration additive `lesson_sections` : `section_type`, `summary`, `language`, `metadata` | Phase 1 |
| 3 | `services/document_service.py` (assemblage, sans embedding) | Phase 1, 2 |
| 4 | `services/chunking_service.py` (découpage sémantique, respect "1 slide = 1 idée") | Phase 3 |
| 5 | `chunk_skills` (si nécessaire après vérification de la relation existante — §18) | Phase 4 |
| 6 | `chunk_knowledge_nodes` | Phase 4 |
| 7 | Niveaux pédagogiques au niveau du chunk (déjà couvert par le schéma cible §7 ci-dessus) | Phase 1 |
| 8 | `services/embedding_service.py`, config `EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` | Phase 1 |
| 9 | `scripts/generate_documents.py` + `generate_chunks.py` sur le contenu existant (95 leçons, ~300+ sections estimées, 22 ressources, 24 termes de glossaire, 16 nœuds) | Phases 3, 4 |
| 10 | `scripts/generate_embeddings.py` | Phase 8, 9 |
| 11 | `scripts/validate_knowledge_base.py` + tests de non-régression et de provenance | Toutes les précédentes |

Chaque phase = une migration Alembic distincte, un commit Git logique distinct (une fois R1 résolu), validée avant la suivante — conformément à la méthode imposée en §35 de la mission.

---

## 9. Impact sur le backend

- **Aucun modèle existant à modifier** en Phase 1 (additif pur : nouveaux fichiers `models/document.py`, `models/chunk.py`, `models/embedding.py`, à ajouter à `app/models/__init__.py`).
- **`requirements.txt`** : ajouter `pgvector` (client Python) ; le modèle d'embedding (Phase 8) ajoutera sa propre dépendance selon le choix fait (ex. `sentence-transformers`, ou un client API externe — à trancher, non présumé ici).
- **`lesson_sections`** (Phase 2) : ajout de colonnes nullables, donc rétrocompatible avec le code actuel (`LessonSectionOut` dans `schemas/progress.py` n'a pas besoin de changer immédiatement).
- **Nouveaux services isolés** (`document_service.py`, `chunking_service.py`, `embedding_service.py`) : n'interfèrent avec aucun service existant. Le seul point de contact naturel est `pdf_import_service.py`, qui produit déjà des `LessonSection` — une future intégration (hors mission actuelle) pourrait déclencher `document_service` après un import PDF, mais ce n'est pas demandé avant la Phase 3 et ne doit pas être anticipé.

## 10. Impact potentiel sur le frontend

**Aucun impact requis pour les Phases 0 à 11** telles que décrites dans la mission — toutes les nouvelles tables et tous les nouveaux services sont invisibles depuis l'API publique tant qu'aucune route `/api/...` n'est créée pour les exposer, et aucune n'est demandée dans ce plan.

Point de vigilance pour une phase *future*, non couverte ici : si une UI de retrieval/chat RAG est un jour construite (Phase "architecture future du RAG", §32 de la mission, explicitement non implémentée maintenant), elle consommera probablement `ai_conversations`/`ai_messages` (déjà modélisées, déjà utilisées nulle part côté frontend non plus) plutôt que les tables `chunks`/`embeddings` directement.

---

## 11. Prochaine étape

Ce rapport n'engage aucune modification. Avant de démarrer la Phase 1 (création des tables `documents`/`chunks`/`embeddings`), il manque deux décisions qui ne se déduisent pas du code existant :

1. **Modèle d'embedding et dimension** (nécessaire pour la colonne `vector(dimension)` — §30 de la mission interdit d'inventer cette valeur).
2. **Confirmation du choix R1** (initialiser Git avant de continuer, ou accepter de travailler sans filet).

En attente de validation avant de passer à la Phase 1.
