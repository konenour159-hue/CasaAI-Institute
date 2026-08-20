# CASA AI Institute — Plateforme e-learning

Ce dépôt contient la mise en œuvre progressive des cahiers des charges
fonctionnel et technique, à partir du prototype `CASA_AI_Institute_V2.html`.

## Structure

```
.
├── db/
│   ├── schema.sql                 # schéma PostgreSQL de référence (56 tables)
│   └── provision_extensions.sql   # extensions à créer une fois par un superuser
├── backend/                       # API FastAPI (voir backend/README.md)
│   ├── app/
│   │   ├── models/                 # modèles SQLAlchemy (miroir de db/schema.sql)
│   │   ├── core/                    # config, sécurité (JWT, hachage)
│   │   ├── db/                      # session SQLAlchemy
│   │   ├── api/                     # routes FastAPI + dépendances d'autorisation
│   │   ├── services/                # logique métier
│   │   └── repositories/            # accès aux données
│   ├── migrations/                 # Alembic (0001_initial_schema = db/schema.sql)
│   ├── scripts/seed.py              # recharge le contenu du prototype en base
│   ├── data/casa_data.json          # export de CASA_DATA (prototype HTML)
│   ├── Dockerfile
│   └── docker-entrypoint.sh
├── docker-compose.yml              # postgres + redis + backend + frontend
└── .env.docker.example             # modèle de configuration Docker Compose
```

Le frontend React/TypeScript (§3 cahier technique) est maintenant scaffoldé
dans `frontend/` — voir `frontend/README.md`.

## Démarrage avec Docker (recommandé)

```bash
cp .env.docker.example .env
# éditer .env si besoin (mots de passe, ports...)

docker compose up --build
```

Cela démarre PostgreSQL (avec pgvector, extensions provisionnées
automatiquement via `db/provision_extensions.sql` monté dans
`/docker-entrypoint-initdb.d/`), Redis, et le backend FastAPI — qui applique
automatiquement les migrations Alembic à chaque démarrage
(`docker-entrypoint.sh`) avant de lancer `uvicorn`.

L'API est alors disponible sur `http://localhost:8000`, documentation
interactive sur `http://localhost:8000/docs`.

Pour charger le contenu pédagogique du prototype (écoles, cours, leçons...) :

```bash
docker compose exec backend python -m scripts.seed
```

### Limite connue de cet environnement de développement

Le `docker-compose.yml` et le `Dockerfile` ont été validés statiquement ici
(`docker compose config`, `hadolint`, tests shell) mais **pas exécutés de
bout en bout** : cet environnement bloque l'accès aux registres d'images
Docker (Docker Hub notamment). La stack a en revanche été testée
composant par composant en installation native (PostgreSQL 16 + pgvector,
migrations Alembic, seed, API FastAPI avec tous les flux d'authentification)
— voir `backend/README.md` pour le détail des tests réels effectués à chaque
étape. Un `docker compose up --build` sur une machine avec accès normal à
Internet devrait fonctionner directement ; à confirmer lors du premier essai
réel.

## Démarrage sans Docker

Voir `backend/README.md` (installation manuelle de PostgreSQL, variables
d'environnement, migrations, seed).

## Roadmap

1. ~~Cahier des charges~~ ✓
2. ~~Modèle de données~~ ✓ (`db/schema.sql`, `app/models/`)
3. ~~Configuration & session DB~~ ✓ (`app/core/config.py`, `app/db/session.py`)
4. ~~Seed du contenu~~ ✓ (`scripts/seed.py`)
5. ~~Authentification~~ ✓ (`app/api/auth.py`, JWT, rôles)
6. ~~Docker~~ ✓ (`docker-compose.yml`, `Dockerfile`)
7. ~~Endpoints de lecture du contenu~~ ✓ (`/api/courses`, `/api/pathways`,
   `/api/schools`, `/api/skills`, `/api/labs`)
8. ~~Endpoints de progression apprenant~~ ✓ (`/api/lessons/{id}`,
   `/api/lessons/{id}/complete`, quiz avec notation et progression de
   compétence, soumission de labs)
9. ~~Frontend React/TypeScript~~ ✓ (accueil, auth, catalogue, dashboard,
   leçon avec niveaux de profondeur, quiz avec corrigé, soumission de labs)
10. ~~Portfolio et certifications~~ ✓ (backend : CRUD preuves, catalogue
    certifications, évaluation d'éligibilité réelle ; frontend : pages
    `/app/portfolio` et `/app/certifications` câblées)
11. ~~Administration (socle)~~ ✓ — gestion utilisateurs (recherche,
    rôle/statut, suppression, garde-fous anti-auto-verrouillage), gestion
    cours/leçons (CRUD complet + workflow brouillon/publication), **import
    de cours depuis un PDF** (extraction réelle, testée avec un vrai
    fichier). Reste côté admin : parcours, compétences, labs, quiz
    (composition manuelle), ressources, critères de certification
    structurés, analytics.
12. Tuteur IA (V5), RAG et LLM local (V6)
