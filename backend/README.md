# CASA AI Institute — Backend (modèle de données + configuration)

Ce dossier contient les briques **modèle de données** et **configuration /
connexion DB** décidées aux étapes 2 et 3 : modèles SQLAlchemy 2.0, migration
Alembic initiale, et infrastructure de connexion PostgreSQL pilotée par
variables d'environnement. Le reste de l'arborescence FastAPI (`api/`,
`services/`, `repositories/`, `auth/`) sera ajouté aux étapes suivantes.

## Contenu

```
backend/
├── app/
│   ├── models/           # 12 modules, 55 tables au total (miroir de db/schema.sql)
│   ├── core/
│   │   └── config.py      # Settings (Pydantic), lit les variables d'environnement
│   └── db/
│       └── session.py     # engine SQLAlchemy + SessionLocal + dépendance get_db
├── migrations/
│   ├── env.py             # cible Base.metadata, URL lue via app.core.config.Settings
│   └── versions/
│       └── 0001_initial_schema.py   # crée les 55 tables (exécute db/schema.sql)
├── alembic.ini
├── .env.example            # modèle à copier en .env (jamais versionné)
└── requirements.txt
```

## Prérequis

Un PostgreSQL 15+ avec les extensions `pgcrypto`, `citext` et `vector`
(pgvector) installées. En développement, ce sera le service `postgres` du
`docker-compose.yml` (à créer à l'étape "Docker" de la roadmap).

**Important (vérifié en conditions réelles) :** la création de ces extensions
demande des droits superuser PostgreSQL. L'utilisateur applicatif (`casa`
dans les exemples ci-dessous) n'a normalement pas ce droit — c'est voulu en
production. Il faut donc, une seule fois, exécuter :

```bash
psql -U postgres -d casa_dev -f ../db/provision_extensions.sql
```

avant tout `alembic upgrade head`. La migration initiale contient bien des
`CREATE EXTENSION IF NOT EXISTS`, mais ceux-ci échoueront si l'utilisateur
applicatif n'a pas les droits et que l'extension n'existe pas encore.

## Utilisation

```bash
cp .env.example .env
# éditer .env avec de vraies valeurs locales

pip install -r requirements.txt

# Appliquer la migration initiale (crée les 55 tables)
alembic upgrade head

# Vérifier l'état
alembic current

# Revenir en arrière si besoin (supprime tout)
alembic downgrade base
```

Dans le code applicatif (FastAPI, à venir), la config et la session
s'utilisent ainsi :

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings

@router.get("/example")
def example(db: Session = Depends(get_db)):
    ...
```

## Tests automatisés

`tests/` — socle pytest, ajouté pour combler l'absence totale de tests
constatée lors d'un audit du site (aucun test, ni backend ni frontend).
Tourne contre la vraie base Postgres du projet (pas de SQLite, pas de
mocks) : chaque test s'exécute dans sa propre transaction, jamais commitée
(`join_transaction_mode="create_savepoint"`, cf. `tests/conftest.py`) —
vérifié en conditions réelles qu'aucune donnée de test ne persiste après la
suite (comparaison des comptes en base avant/après).

Périmètre actuel : authentification (inscription, doublon d'email, connexion,
message d'erreur générique login, mot de passe oublié/réinitialisation, refus
d'un access token comme token de réinitialisation, changement de mot de
passe) et notation des quiz (score, seuil de réussite, question sans réponse,
question hors quiz, progression de compétence sur réussite/échec) — les deux
zones désignées comme priorité par l'audit. À étendre au fil des prochains
changements plutôt que de viser une couverture exhaustive d'un coup.

```bash
pip install -r requirements-dev.txt   # une fois par environnement (jamais dans l'image de prod)
pytest                                 # depuis backend/
```

17 tests, tous passants.

## Seed du contenu pédagogique

`data/casa_data.json` est un export du `window.CASA_DATA` du prototype
(`CASA_AI_Institute_V2.html`). Le script `scripts/seed.py` le charge dans les
56 tables via les modèles SQLAlchemy — écoles, compétences, parcours, cours,
leçons (avec objectifs, sections et les 6 niveaux de profondeur), labs,
questions/banques de questions, ressources, glossaire, graphe de
connaissances, normes de gouvernance et certifications.

```bash
python -m scripts.seed
```

Le script est **idempotent** (relançable sans dupliquer, testé en conditions
réelles). Il ne crée **aucun utilisateur ni donnée de progression** — cela
viendra avec l'authentification.

Point d'attention découvert en testant : les relations `knowledgeGraph.usedIn`
du prototype pointent en réalité vers des **leçons**, pas vers d'autres nœuds
du graphe comme le nom le laissait supposer. La table
`knowledge_node_used_in_lessons` reflète cette réalité (vérifié
empiriquement : 33/33 valeurs de `usedIn` sont des identifiants de leçon).

Les critères de certification du prototype (`requirements`, texte libre comme
« Quiz ≥ 75 % ») sont convertis heuristiquement vers le type structuré
`certification_requirements` (détection d'un pourcentage → `MIN_SCORE`,
sinon → `EVIDENCE` générique). À affiner manuellement depuis l'admin une fois
le CMS disponible.

## Authentification

`app/main.py` expose l'API FastAPI avec les routes d'auth (§5 cahier
fonctionnel, §5 cahier technique) :

```
POST /api/auth/register   → 201, crée un compte LEARNER (le rôle n'est
                             jamais fourni par le client)
POST /api/auth/login      → 200, vérifie existence/mot de passe/statut du
                             compte, renvoie {access_token, refresh_token}
POST /api/auth/refresh    → 200, échange un refresh token contre un nouvel
                             access token
POST /api/auth/logout     → 204 (tokens JWT stateless en V1, voir limitation
                             documentée dans app/core/security.py)
GET  /api/auth/me         → 200, profil de l'utilisateur courant
```

Lancer l'API en développement :

```bash
uvicorn app.main:app --reload
# puis http://localhost:8000/docs pour la documentation interactive
```

**Autorisation** (§9 CDC technique — contrôles centralisés dans des
dépendances FastAPI) : `app/api/deps.py` fournit `get_current_user` (valide
le token, recharge l'utilisateur depuis la base à chaque requête — un compte
suspendu ou un changement de rôle prend effet immédiatement) et
`require_role(*roles)` / `require_admin` pour restreindre une route par rôle.
Un `LEARNER` qui appelle une route protégée `require_admin` reçoit un `403`,
y compris en tapant l'URL directement (§5.4 cahier fonctionnel).

**Tests effectués en conditions réelles** (PostgreSQL 16 + pgvector,
`TestClient` FastAPI, pas de mocks) : inscription, doublon d'email (409),
mauvais mot de passe (401), connexion réussie, `/me` avec/sans/mauvais token
(200/401/401), refresh (200, nouveau token différent), refus d'utiliser un
access token comme refresh token (401), logout (204), contrôle de rôle
`LEARNER` vs `ADMIN` (403/200), compte suspendu rejeté à la connexion (401),
validations Pydantic (mot de passe court, email invalide → 422).

## Endpoints de contenu (lecture publique)

```
GET /api/schools                       → liste des écoles
GET /api/skills?school_id=...          → liste des compétences (filtre optionnel)
GET /api/courses?school_id=&level=&limit=&offset=
                                        → liste paginée des cours publiés
GET /api/courses/{id}                  → détail d'un cours + ses leçons (résumé)
GET /api/pathways?level=&limit=&offset=
                                        → liste paginée des parcours publiés
GET /api/pathways/{id}                 → détail d'un parcours + ses cours
```

Aucune authentification requise (§4.1 cahier fonctionnel — catalogue public).
Seul le contenu au statut `PUBLISHED` est exposé ; testé empiriquement en
basculant un cours en `DRAFT` et en vérifiant sa disparition de la liste et
un `404` sur son détail, avant restauration et vérification qu'aucune donnée
(cours, leçons) n'avait été perdue.

Le détail d'un cours n'expose que le **résumé** de chaque leçon (titre,
niveau, durée, position) — pas son contenu complet (sections, objectifs,
niveaux de profondeur). Décision produit assumée : le contenu pédagogique
complet d'une leçon sera exposé via un futur `/api/lessons/{id}`, réservé
aux utilisateurs authentifiés (prochaine étape : progression apprenant).

**Point d'attention technique documenté dans le code** : `Course.lessons` et
`Pathway.courses` sont des relations SQLAlchemy chargées en mémoire ; le
repository de contenu (`content_repository.py`) évite délibérément de leur
réaffecter une sous-liste filtrée (technique de filtrage naïve mais
dangereuse), car `Course.lessons` porte `cascade="all, delete-orphan"` — un
`commit()` ultérieur sur la même session aurait pu supprimer les leçons
exclues du filtre. Les collections filtrées sont donc toujours renvoyées à
part, jamais réassignées sur l'objet ORM.

## Endpoints de progression apprenant (authentifiés)

```
GET  /api/lessons/{id}                 → contenu complet de la leçon (sections,
                                          objectifs, 6 niveaux de profondeur)
POST /api/lessons/{id}/complete        → marque la leçon comme terminée
GET  /api/me/progress                  → progression de l'utilisateur sur ses leçons
GET  /api/me/skills                    → niveaux de maîtrise par compétence

GET  /api/quizzes/{id}                 → questions + options (jamais la bonne réponse)
GET  /api/skills/{id}/quiz             → retrouve le quiz d'entraînement d'une
                                          compétence sans connaître son UUID
                                          (utilisé par le bouton "S'entraîner"
                                          du dashboard frontend)
POST /api/quizzes/{id}/attempt         → soumet des réponses, renvoie score/corrigé
GET  /api/me/quiz-history              → historique des tentatives

GET  /api/labs                         → catalogue des labs (public, comme les cours)
GET  /api/labs/{id}                    → détail d'un lab (public)
POST /api/labs/{id}/submit             → soumet un travail de lab (authentifié)
GET  /api/me/lab-results               → historique des soumissions de labs
```

**Règle de progression de compétence (§16 cahier fonctionnel)** : une
tentative de quiz réussie fait progresser d'un niveau (`mastery_level`,
plafonné à 4) la compétence associée au quiz, si définie. Règle volontairement
simple pour la V1 — à affiner (pondération par difficulté, décroissance dans
le temps...) si le besoin se confirme.

**Quiz de pratique générés automatiquement** : aucune interface
d'administration ne permet encore de composer des quiz manuellement (viendra
avec le CMS). `scripts/seed.py` assemble donc un quiz d'entraînement par
compétence à partir des questions existantes (jusqu'à 10 questions chacun,
23 quiz générés) — solution pragmatique et idempotente en attendant le CMS.

**Tests effectués en conditions réelles** : contenu complet d'une leçon
(objectifs/sections/6 niveaux de profondeur) accessible authentifié / refusé
sans auth (401) ; complétion de leçon reflétée dans `/api/me/progress` ;
quiz — aucune fuite de la bonne réponse dans `GET`, tentative avec 100% de
bonnes réponses → score 100 + compétence +1, tentative 100% fausse → score 0
+ échec, question hors quiz → 422 ; labs — soumission enregistrée et
retrouvée dans l'historique, lab inexistant → 404.

## Endpoints portfolio et certifications (§17, §18 cahier fonctionnel)

```
POST /api/portfolio/evidence                          → créer une preuve (authentifié)
GET  /api/me/portfolio                                 → mes preuves
GET  /api/portfolio/evidence/{id}                      → détail (uniquement la sienne, 404 sinon)

GET  /api/certifications                               → catalogue (public)
GET  /api/certifications/{id}                          → détail + critères (public)
GET  /api/me/certifications/{id}/eligibility           → évaluation d'éligibilité (authentifié)
```

**Évaluation d'éligibilité — honnêteté délibérée** (`app/services/certification_service.py`) :
seuls les critères objectivement vérifiables à partir des données stockées
sont évalués automatiquement :
- `COURSE` → toutes les leçons publiées du cours sont `COMPLETED`
- `LAB` → un `LabResult.completed=True` existe
- `SKILL` → `mastery_level >= 2/4`
- `MIN_SCORE` (si lié à une compétence) → meilleur score de quiz ≥ seuil

Les critères `EVIDENCE`/`FINAL_PROJECT`, et la quasi-totalité des critères
hérités du prototype (texte libre sans référence structurée — vérifié en
base : 12 des 13 critères actuels), renvoient `satisfied: null` — jamais un
faux `true`. `eligible` n'est `true` que si **tous** les critères sont
vérifiés ET satisfaits.

**Tests réels effectués** : isolation cross-utilisateur du portfolio (404 sur
la preuve d'un autre), calcul d'éligibilité sur une certification aux
critères 100% texte libre (`eligible: False`, tous `satisfied: null`), puis
sur une certification de test à critères structurés — un apprenant a
réellement terminé toutes les leçons d'un cours et soumis un lab,
`eligible` passe à `True` avec le détail correct ; testé aussi le cas
partiel (une seule leçon sur plusieurs complétée → `satisfied: False`,
`eligible: False`).

## Endpoints admin (§22 cahier fonctionnel) — réservés au rôle ADMIN

```
GET    /api/admin/users                     → liste (recherche, filtres rôle/statut, pagination)
GET    /api/admin/users/{id}                → détail
PATCH  /api/admin/users/{id}                → changer rôle et/ou statut
DELETE /api/admin/users/{id}                → suppression définitive

GET    /api/admin/courses                   → liste TOUS statuts (public = PUBLISHED uniquement)
GET    /api/admin/courses/{id}
POST   /api/admin/courses
PUT    /api/admin/courses/{id}
DELETE /api/admin/courses/{id}

GET    /api/admin/lessons?course_id=...     → liste TOUS statuts
GET    /api/admin/lessons/{id}
POST   /api/admin/lessons                   → objectifs/sections/niveaux de
                                               profondeur en une seule requête
PUT    /api/admin/lessons/{id}              → remplace intégralement le
                                               contenu imbriqué (même principe
                                               idempotent que scripts/seed.py)
DELETE /api/admin/lessons/{id}

POST   /api/admin/courses/import-pdf        → multipart (school_id + file),
                                               crée cours+leçon en DRAFT
```

**Garde-fous testés** : un admin ne peut ni changer son propre rôle, ni
suspendre ou supprimer son propre compte (`400`, message explicite) — évite
qu'une plateforme se retrouve sans administrateur actif. Un `LEARNER` reçoit
`403` sur toutes ces routes.

**Import PDF — portée assumée** : extraction de texte brute (`pypdf`), une
section par leçon par page de PDF, statut `DRAFT` systématique — une
relecture et une republication manuelles restent nécessaires. Aucune
structuration intelligente (titres détectés, découpage sémantique) : cela
demanderait un LLM, non câblé dans le backend (prévu V5, tuteur IA/RAG).
Testé avec un vrai PDF généré (3 pages, texte réel), y compris les cas
limites : PDF illisible, fichier non-PDF (`422`), école inexistante (`422`).
Un PDF scanné (sans couche de texte) produit un avertissement explicite
plutôt qu'un échec silencieux.

**Tests réels effectués** : cycle complet créer → publier (invisible en
DRAFT côté public, visible après passage à PUBLISHED, vérifié sur le
catalogue public réel) → modifier → supprimer, pour cours et leçons ;
remplacement du contenu imbriqué (objectifs/sections/niveaux) vérifié ;
suspension d'un compte testée en conditions réelles (le compte suspendu ne
peut plus se connecter, `401`).

## Étapes suivantes de la roadmap

1. Frontend pour les entités admin restantes : parcours, compétences, labs,
   quiz (composition manuelle), ressources, certifications (critères
   structurés — actuellement seule une insertion SQL directe le permet)
2. Analytics (§24 cahier fonctionnel)
3. Tuteur IA (V5), RAG et LLM local (V6)

