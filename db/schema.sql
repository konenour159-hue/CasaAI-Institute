-- =============================================================================
-- CASA AI Institute — Schéma PostgreSQL (V1)
-- =============================================================================
-- Ce script est la référence de conception. La création réelle des tables en
-- environnement de développement se fera via des migrations Alembic générées
-- à partir des modèles SQLAlchemy (backend/app/models/), pas en exécutant ce
-- fichier directement en production.
--
-- Conventions :
--   - clés primaires : UUID (gen_random_uuid()) sauf tables de catalogue issues
--     du prototype, qui gardent leur identifiant texte lisible existant
--     (ex. skills.id = 'ai-literacy') pour permettre un seed direct depuis
--     CASA_DATA sans re-mapper les références.
--   - horodatage : created_at / updated_at en timestamptz, gérés par défaut
--     serveur (now()) puis par trigger applicatif ou Alembic.
--   - suppressions : ON DELETE RESTRICT par défaut sur le contenu pédagogique
--     (on ne supprime pas un cours référencé par un parcours sans le retirer
--     explicitement) ; ON DELETE CASCADE sur les données strictement liées à
--     un utilisateur (sa progression, ses tentatives, etc.).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "citext";     -- email insensible à la casse
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector, pour le RAG (V6) — sans impact ici, préparé à l'avance

-- =============================================================================
-- 1. UTILISATEURS, RÔLES, PROFIL D'ONBOARDING
-- =============================================================================

-- ADMIN : gestion de contenu uniquement (cours/leçons/import PDF).
-- SUPER_ADMIN : sur-ensemble d'ADMIN + utilisateurs, progression globale,
-- certifications (voir migrations 0002/0003 et backend/app/api/deps.py).
CREATE TYPE user_role AS ENUM ('ADMIN', 'SUPER_ADMIN', 'LEARNER');
CREATE TYPE account_status AS ENUM ('ACTIVE', 'SUSPENDED', 'PENDING');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           CITEXT NOT NULL UNIQUE,          -- nécessite l'extension citext (voir note)
    password_hash   TEXT NOT NULL,
    role            user_role NOT NULL DEFAULT 'LEARNER',
    status          account_status NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);
-- NOTE: si l'extension citext n'est pas disponible, remplacer CITEXT par TEXT
-- et gérer l'unicité insensible à la casse au niveau applicatif (lower(email)).

-- Catalogue des "profils" du prototype (Direction, Manager, Consultant, Data
-- Engineer...). Contenu de référence, gérable depuis /admin/settings.
CREATE TABLE learner_profile_types (
    id              TEXT PRIMARY KEY,        -- ex: 'consultant', 'data-engineer'
    name            TEXT NOT NULL,
    description     TEXT
);

-- Catalogue des objectifs proposés à l'onboarding.
CREATE TABLE goals (
    id              TEXT PRIMARY KEY,        -- ex: 'literacy', 'usecases'
    label           TEXT NOT NULL
);

-- Informations d'onboarding + préférences, en relation 1-1 avec l'utilisateur.
-- NOTE: default_pathway_id est ajouté plus bas via ALTER TABLE (section 3),
-- une fois la table `pathways` créée, pour éviter une référence en avant.
CREATE TABLE user_profiles (
    user_id                 UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    profile_type_id         TEXT REFERENCES learner_profile_types(id) ON DELETE SET NULL,
    level                   TEXT,                     -- niveau déclaré à l'onboarding
    career_objectives       TEXT,
    onboarding_done         BOOLEAN NOT NULL DEFAULT FALSE,
    theme                   TEXT NOT NULL DEFAULT 'light',
    reduced_motion          BOOLEAN NOT NULL DEFAULT FALSE,
    language                TEXT NOT NULL DEFAULT 'fr',
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_profile_goals (
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    goal_id     TEXT REFERENCES goals(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, goal_id)
);

-- NOTE: user_profile_interest_skills ("compétences déjà acquises" à
-- l'onboarding, §7 cahier fonctionnel) est créée en section 2, juste après
-- la table `skills`, pour éviter une référence en avant.

-- =============================================================================
-- 2. RÉFÉRENTIEL PÉDAGOGIQUE : ÉCOLES, COMPÉTENCES
-- =============================================================================

CREATE TABLE schools (
    id              TEXT PRIMARY KEY,        -- ex: 'genai', 'rag', 'governance'
    name            TEXT NOT NULL,
    short_name      TEXT NOT NULL,
    color           TEXT NOT NULL,           -- code couleur hex, cosmétique
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE skills (
    id              TEXT PRIMARY KEY,        -- ex: 'ai-literacy', 'rag-design'
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "Compétences déjà acquises" déclarées par l'apprenant à l'onboarding
-- (§7 cahier fonctionnel). Placée ici (après `skills`) pour éviter toute
-- référence en avant depuis la section 1.
CREATE TABLE user_profile_interest_skills (
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    skill_id    TEXT REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, skill_id)
);

-- =============================================================================
-- 3. CONTENU : PARCOURS, COURS, LEÇONS
-- =============================================================================

CREATE TYPE content_status AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED');

CREATE TABLE pathways (
    id                  TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    profile_label       TEXT,                -- libellé libre affiché (ex: "Direction")
    level               TEXT,                -- ex: 'N1–N2'
    duration_label      TEXT,                -- ex: '12 h' (affichage)
    color               TEXT,
    description         TEXT,
    status              content_status NOT NULL DEFAULT 'DRAFT',
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Complète user_profiles (section 1) maintenant que `pathways` existe.
ALTER TABLE user_profiles
    ADD COLUMN default_pathway_id TEXT REFERENCES pathways(id) ON DELETE SET NULL;

CREATE TABLE pathway_prerequisites (
    pathway_id              TEXT REFERENCES pathways(id) ON DELETE CASCADE,
    prerequisite_pathway_id TEXT REFERENCES pathways(id) ON DELETE CASCADE,
    PRIMARY KEY (pathway_id, prerequisite_pathway_id),
    CHECK (pathway_id <> prerequisite_pathway_id)
);

CREATE TABLE pathway_skills (
    -- compétences visées par le parcours (§10 cahier fonctionnel)
    pathway_id  TEXT REFERENCES pathways(id) ON DELETE CASCADE,
    skill_id    TEXT REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (pathway_id, skill_id)
);

CREATE TABLE courses (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,
    title           TEXT NOT NULL,
    level           TEXT,
    duration_min    INTEGER,                 -- durée en minutes
    color           TEXT,
    description     TEXT,
    status          content_status NOT NULL DEFAULT 'DRAFT',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE course_prerequisites (
    course_id               TEXT REFERENCES courses(id) ON DELETE CASCADE,
    prerequisite_course_id  TEXT REFERENCES courses(id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, prerequisite_course_id),
    CHECK (course_id <> prerequisite_course_id)
);

CREATE TABLE course_skills (
    course_id   TEXT REFERENCES courses(id) ON DELETE CASCADE,
    skill_id    TEXT REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, skill_id)
);

CREATE TABLE pathway_courses (
    pathway_id  TEXT REFERENCES pathways(id) ON DELETE CASCADE,
    course_id   TEXT REFERENCES courses(id) ON DELETE RESTRICT,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (pathway_id, course_id)
);

CREATE TABLE demos (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT,
    -- le prototype code chaque démo "en dur" (composant JS). En V1 on garde une
    -- référence à un identifiant de composant frontend ; en V2 on pourra passer
    -- à un contenu configurable (JSON de paramètres) pour un rendu générique.
    component_key   TEXT,
    status          content_status NOT NULL DEFAULT 'PUBLISHED',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lessons (
    id              TEXT PRIMARY KEY,
    course_id       TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    skill_id        TEXT REFERENCES skills(id) ON DELETE SET NULL,
    demo_id         TEXT REFERENCES demos(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    level           TEXT,
    duration_min    INTEGER,
    summary         TEXT,
    example         TEXT,
    position        INTEGER NOT NULL DEFAULT 0,      -- ordre dans le cours
    status          content_status NOT NULL DEFAULT 'DRAFT',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lesson_objectives (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id   TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    label       TEXT NOT NULL
);

-- Structure de la leçon (§12 cahier fonctionnel) : sections ordonnées.
-- "Introduction / Contexte / Objectifs / Concepts / Démonstration /
--  Mise en pratique / Filiation / Quiz / Synthèse" correspond aux sections
-- + aux relations demo_id / quiz déjà modélisées séparément.
CREATE TABLE lesson_sections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id   TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    image_url   TEXT,
    image_alt   TEXT
);

-- Lecture à plusieurs niveaux de profondeur d'une même leçon (onglets du
-- prototype : Essentiel / Technique / Mathématiques / Implémentation /
-- Architecture / Gouvernance & risques). Optionnel : une leçon peut n'avoir
-- aucun, un ou les six niveaux renseignés.
CREATE TYPE lesson_depth_key AS ENUM (
    'ESSENTIAL', 'TECHNICAL', 'MATHEMATICS', 'IMPLEMENTATION', 'ARCHITECTURE', 'GOVERNANCE'
);

CREATE TABLE lesson_depth_levels (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id   TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    depth_key   lesson_depth_key NOT NULL,
    label       TEXT NOT NULL,        -- ex: 'Essentiel' (libellé affiché de l'onglet)
    title       TEXT NOT NULL,        -- ex: 'Comprendre le rôle de la notion'
    body        TEXT NOT NULL,
    UNIQUE (lesson_id, depth_key)
);

-- =============================================================================
-- 4. LABORATOIRES
-- =============================================================================

CREATE TABLE labs (
    id              TEXT PRIMARY KEY,
    school_id       TEXT REFERENCES schools(id) ON DELETE SET NULL,
    lesson_id       TEXT REFERENCES lessons(id) ON DELETE SET NULL,  -- rattachement optionnel
    title           TEXT NOT NULL,
    level           TEXT,
    duration_min    INTEGER,
    color           TEXT,
    description     TEXT,             -- correspond à l'Énoncé (§14)
    environment     TEXT,             -- Environnement
    instructions    TEXT,             -- Instructions
    dataset_ref     TEXT,             -- Données (référence/URL)
    deliverable     TEXT,             -- Travail demandé
    evaluation_note TEXT,             -- Évaluation (critères)
    status          content_status NOT NULL DEFAULT 'DRAFT',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lab_skills (
    lab_id      TEXT REFERENCES labs(id) ON DELETE CASCADE,
    skill_id    TEXT REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (lab_id, skill_id)
);

CREATE TABLE lab_modes (
    -- ex: 'Guidé', 'Exploration', 'Challenge'
    lab_id      TEXT REFERENCES labs(id) ON DELETE CASCADE,
    mode        TEXT NOT NULL,
    PRIMARY KEY (lab_id, mode)
);

-- =============================================================================
-- 5. QUIZ ET BANQUES DE QUESTIONS
-- =============================================================================

CREATE TABLE question_banks (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE questions (
    id              TEXT PRIMARY KEY,       -- ex: 'Q001'
    bank_id         TEXT REFERENCES question_banks(id) ON DELETE SET NULL,
    skill_id        TEXT REFERENCES skills(id) ON DELETE SET NULL,
    domain          TEXT,
    difficulty      SMALLINT NOT NULL DEFAULT 1,
    question_text   TEXT NOT NULL,
    explanation     TEXT,
    status          content_status NOT NULL DEFAULT 'DRAFT',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE question_options (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    position        INTEGER NOT NULL,
    option_text     TEXT NOT NULL,
    is_correct      BOOLEAN NOT NULL DEFAULT FALSE
);

-- Un quiz réel : entraînement, validation d'une leçon/cours, ou évaluation
-- finale (§15 cahier fonctionnel). Assemble des questions du référentiel.
CREATE TYPE quiz_kind AS ENUM ('PRACTICE', 'VALIDATION', 'FINAL');

CREATE TABLE quizzes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    kind            quiz_kind NOT NULL DEFAULT 'PRACTICE',
    lesson_id       TEXT REFERENCES lessons(id) ON DELETE CASCADE,
    course_id       TEXT REFERENCES courses(id) ON DELETE CASCADE,
    skill_id        TEXT REFERENCES skills(id) ON DELETE SET NULL,
    pass_threshold  SMALLINT NOT NULL DEFAULT 70,   -- % requis pour réussir
    status          content_status NOT NULL DEFAULT 'DRAFT',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE quiz_questions (
    quiz_id     UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    question_id TEXT REFERENCES questions(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (quiz_id, question_id)
);

-- =============================================================================
-- 6. RESSOURCES, GLOSSAIRE, NORMES / GOUVERNANCE
-- =============================================================================

CREATE TABLE resources (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    type            TEXT,             -- ex: 'Rapport', 'Article'
    publisher       TEXT,
    year            SMALLINT,
    level           TEXT,
    description     TEXT,
    status          content_status NOT NULL DEFAULT 'PUBLISHED',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE resource_tags (
    resource_id TEXT REFERENCES resources(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    PRIMARY KEY (resource_id, tag)
);

-- Associations ressource <-> cours / leçon / compétence (§19 cahier fonctionnel)
CREATE TABLE resource_courses (
    resource_id TEXT REFERENCES resources(id) ON DELETE CASCADE,
    course_id   TEXT REFERENCES courses(id) ON DELETE CASCADE,
    PRIMARY KEY (resource_id, course_id)
);
CREATE TABLE resource_lessons (
    resource_id TEXT REFERENCES resources(id) ON DELETE CASCADE,
    lesson_id   TEXT REFERENCES lessons(id) ON DELETE CASCADE,
    PRIMARY KEY (resource_id, lesson_id)
);
CREATE TABLE resource_skills (
    resource_id TEXT REFERENCES resources(id) ON DELETE CASCADE,
    skill_id    TEXT REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (resource_id, skill_id)
);

CREATE TABLE glossary_terms (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term            TEXT NOT NULL,
    term_en         TEXT,
    definition      TEXT NOT NULL,
    status          content_status NOT NULL DEFAULT 'PUBLISHED',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (term)
);

-- Contenu de référence "Gouvernance" (page Standards du prototype).
-- Éditable depuis l'admin comme le reste du contenu.
CREATE TABLE governance_standards (
    id              TEXT PRIMARY KEY,        -- ex: '42001'
    name            TEXT NOT NULL,           -- ex: 'ISO/IEC 42001'
    purpose         TEXT
);

CREATE TABLE governance_jurisdictions (
    id              TEXT PRIMARY KEY,        -- ex: 'eu', 'us', 'cn'
    name            TEXT NOT NULL,
    focus           TEXT
);

-- =============================================================================
-- 7. GRAPHE DE CONNAISSANCES (page "Connaissances / knowledge")
-- =============================================================================

CREATE TABLE knowledge_nodes (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    stage           TEXT,             -- ex: 'Fondation'
    formula         TEXT,
    guiding_question TEXT,
    status          content_status NOT NULL DEFAULT 'PUBLISHED',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_node_dependencies (
    node_id             TEXT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    depends_on_node_id  TEXT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, depends_on_node_id),
    CHECK (node_id <> depends_on_node_id)
);

-- Leçons qui mobilisent ce concept ("usedIn" dans le prototype). Pointe vers
-- des leçons, pas vers d'autres nœuds du graphe (vérifié empiriquement sur
-- CASA_DATA : 33/33 valeurs de usedIn sont des lesson.id).
CREATE TABLE knowledge_node_used_in_lessons (
    node_id     TEXT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    lesson_id   TEXT REFERENCES lessons(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, lesson_id)
);

CREATE TABLE knowledge_node_applications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id     TEXT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    label       TEXT NOT NULL
);

CREATE TABLE knowledge_node_demos (
    node_id     TEXT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    demo_id     TEXT REFERENCES demos(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, demo_id)
);

CREATE TABLE knowledge_node_labs (
    node_id     TEXT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    lab_id      TEXT REFERENCES labs(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, lab_id)
);

-- =============================================================================
-- 8. CERTIFICATIONS
-- =============================================================================

CREATE TABLE certifications (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    level           TEXT,
    description     TEXT,
    color           TEXT,
    -- seuil global historique du prototype (ex: score minimum agrégé) ;
    -- conservé pour compatibilité, les critères fins vivent dans
    -- certification_requirements ci-dessous (§18 cahier fonctionnel).
    legacy_threshold SMALLINT,
    status          content_status NOT NULL DEFAULT 'DRAFT',
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE certification_requirement_type AS ENUM (
    'COURSE', 'MIN_SCORE', 'LAB', 'SKILL', 'EVIDENCE', 'FINAL_PROJECT'
);

-- Critères structurés définis par l'administrateur (§18) : cours requis,
-- scores minimums, labs requis, compétences requises, preuves requises,
-- projet final. Chaque ligne est un critère atomique et vérifiable.
CREATE TABLE certification_requirements (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    certification_id    TEXT NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    requirement_type    certification_requirement_type NOT NULL,
    course_id           TEXT REFERENCES courses(id) ON DELETE CASCADE,
    lab_id              TEXT REFERENCES labs(id) ON DELETE CASCADE,
    skill_id            TEXT REFERENCES skills(id) ON DELETE CASCADE,
    min_score            SMALLINT,           -- utilisé si requirement_type = MIN_SCORE
    description         TEXT,               -- libellé libre affiché à l'apprenant
    position             INTEGER NOT NULL DEFAULT 0
);

CREATE TYPE user_certification_status AS ENUM ('IN_PROGRESS', 'ELIGIBLE', 'ISSUED', 'REVOKED');

CREATE TABLE user_certifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    certification_id    TEXT NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    status              user_certification_status NOT NULL DEFAULT 'IN_PROGRESS',
    issued_at           TIMESTAMPTZ,
    UNIQUE (user_id, certification_id)
);

-- =============================================================================
-- 9. PROGRESSION, PREUVES, RÉSULTATS (données propres à chaque apprenant)
-- =============================================================================

CREATE TYPE lesson_progress_status AS ENUM ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED');

CREATE TABLE user_lesson_progress (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id       TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    status          lesson_progress_status NOT NULL DEFAULT 'NOT_STARTED',
    progress_pct    SMALLINT NOT NULL DEFAULT 0,
    bookmarked      BOOLEAN NOT NULL DEFAULT FALSE,
    note            TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, lesson_id)
);

CREATE TABLE user_skills (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id        TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    mastery_level   SMALLINT NOT NULL DEFAULT 0,   -- ex: 0..4
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE quiz_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_id         UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    score           SMALLINT NOT NULL,             -- pourcentage
    passed          BOOLEAN NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE quiz_attempt_answers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id          UUID NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id         TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    selected_option_id  UUID REFERENCES question_options(id) ON DELETE SET NULL,
    is_correct          BOOLEAN NOT NULL
);

CREATE TABLE lab_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id          TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    mode            TEXT,                           -- 'Guidé' / 'Exploration' / 'Challenge'
    completed       BOOLEAN NOT NULL DEFAULT FALSE,
    score           SMALLINT,
    submission      JSONB,                          -- contenu libre soumis (réponses, code, fichiers réf.)
    feedback        TEXT,
    submitted_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portfolio_evidence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    context         TEXT,
    problem         TEXT,
    role            TEXT,
    deliverable     TEXT,
    result          TEXT,
    metrics         JSONB,
    feedback        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portfolio_evidence_skills (
    evidence_id     UUID REFERENCES portfolio_evidence(id) ON DELETE CASCADE,
    skill_id        TEXT REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (evidence_id, skill_id)
);

CREATE TABLE demo_views (
    -- traçabilité simple des consultations de démo par l'apprenant
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    demo_id         TEXT NOT NULL REFERENCES demos(id) ON DELETE CASCADE,
    viewed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 10. NOTIFICATIONS
-- =============================================================================

CREATE TYPE notification_type AS ENUM (
    'NEW_ACTIVITY', 'COURSE_COMPLETED', 'QUIZ_PASSED', 'CERTIFICATION_ISSUED',
    'NEW_CONTENT', 'FEEDBACK', 'REMINDER'
);

CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            notification_type NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT,
    read            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 11. TUTEUR IA (conversations) — structure prête dès V1, contenu simulé
--     jusqu'à l'arrivée de l'orchestrateur IA réel (V5/V6, cf. cahier technique §21)
-- =============================================================================

CREATE TABLE ai_conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_type    TEXT,             -- ex: 'lesson', 'general'
    context_id      TEXT,             -- ex: lesson_id si context_type = 'lesson'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE ai_message_role AS ENUM ('USER', 'ASSISTANT');

CREATE TABLE ai_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role            ai_message_role NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 12. INDEX RECOMMANDÉS (au-delà des PK/FK déjà indexées implicitement)
-- =============================================================================

CREATE INDEX idx_lessons_course_id            ON lessons(course_id);
CREATE INDEX idx_lessons_status                ON lessons(status);
CREATE INDEX idx_courses_school_id             ON courses(school_id);
CREATE INDEX idx_user_lesson_progress_user     ON user_lesson_progress(user_id);
CREATE INDEX idx_quiz_attempts_user            ON quiz_attempts(user_id);
CREATE INDEX idx_lab_results_user              ON lab_results(user_id);
CREATE INDEX idx_notifications_user_unread     ON notifications(user_id) WHERE read = FALSE;
CREATE INDEX idx_ai_messages_conversation      ON ai_messages(conversation_id);
CREATE INDEX idx_portfolio_evidence_user       ON portfolio_evidence(user_id);
CREATE INDEX idx_questions_skill_id            ON questions(skill_id);
