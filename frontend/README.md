# CASA AI Institute — Frontend

React 19 + TypeScript + Vite, conforme à l'arborescence du cahier des
charges technique (§3) : `components/`, `pages/`, `layouts/`, `services/`,
`hooks/`, `stores/`, `types/`, `utils/`.

## Démarrage

```bash
npm install
npm run dev
```

Ou via Docker (voir le `README.md` racine) : `docker compose up --build`.

## Structure

- `src/types/api.ts` — miroir manuel des schémas Pydantic du backend
  (`app/schemas/*.py`). Vérifié champ par champ contre les réponses réelles
  de l'API à la construction de ce frontend ; à resynchroniser à la main si
  le backend évolue (pas de génération automatique depuis l'OpenAPI pour
  l'instant).
- `src/services/` — un fichier par domaine (`authService`, `contentService`,
  `progressService`), tous passent par `apiClient.ts`.
- `src/services/apiClient.ts` — client HTTP unique : injecte le token
  d'accès, et gère le rafraîchissement automatique et transparent sur un
  `401` (une seule tentative, puis la requête d'origine est rejouée une fois).
- `src/stores/authStore.tsx` — session utilisateur (React Context). Les
  tokens sont stockés en `localStorage` (pratique standard pour un flux JWT
  par en-tête `Authorization`, distinct de l'interdiction de stocker des
  *données métier* en `localStorage` posée par le cahier fonctionnel §28,
  qui concerne la progression, pas les tokens d'authentification).
- `src/components/ProtectedRoute.tsx` — redirige vers `/login` si non
  authentifié ; utilisé pour toutes les routes `/app/*`.

## Pages livrées dans cette itération

```
/                       accueil public
/login, /register       authentification
/catalog                 catalogue public (parcours, cours, labs)
/courses/:id              détail d'un cours (public), liste des leçons
/labs/:id                 détail d'un lab (public) + formulaire de
                          soumission (authentifié)
/app/dashboard            (protégé) progression réelle + compétences,
                          lien "S'entraîner" vers le quiz de chaque compétence
/app/lessons/:id           (protégé) contenu complet d'une leçon, 6 niveaux
                          de profondeur en onglets, bouton de complétion
/app/skills/:id/practice   (protégé) passage du quiz d'entraînement de la
                          compétence, corrigé détaillé après soumission
/app/portfolio             (protégé) mes preuves + formulaire d'ajout
/app/certifications        (protégé) catalogue des certifications
/app/certifications/:id     (protégé) critères + éligibilité réelle
                          (✓ satisfait, ✗ non satisfait, ? revue manuelle
                          nécessaire — jamais un faux "satisfait")

/admin/users               (admin) recherche, changement de rôle/statut,
                          suppression — garde-fous anti-auto-verrouillage
/admin/courses             (admin) liste tous statuts, création, publication
/admin/courses/:id          (admin) leçons du cours
/admin/courses/:id/lessons/:lessonId ou /new
                          (admin) éditeur complet : objectifs, sections,
                          niveaux de profondeur (listes dynamiques)
/admin/import-pdf          (admin) upload PDF → cours+leçon en brouillon
```

Reste : bibliothèque/glossaire côté apprenant ; côté admin, parcours,
compétences, labs, quiz (composition manuelle), ressources, critères de
certification structurés, et analytics.

**Nouvel endpoint backend ajouté au fil des itérations** : `GET /api/skills/{id}/quiz`
— les quiz générés par le seed n'étaient découvrables que par UUID exact ;
cet endpoint permet au dashboard de proposer "S'entraîner" sur une compétence
sans connaître cet UUID à l'avance.

## Design

Système de tokens CSS dans `src/index.css` : palette indigo profond + accents
or (réussite/certification) et teal (progression), typographie Space
Grotesk/IBM Plex Sans/IBM Plex Mono. La séquence pédagogique du cahier
fonctionnel (Découvrir → … → Certifier, 8 étapes) est utilisée comme motif
signature sur la page d'accueil — justifié car c'est une vraie séquence
déjà nommée dans le cahier des charges, pas un ornement.

## Tests effectués

- `npx tsc --noEmit` : aucune erreur de type (deux fois, avant/après ajout
  quiz+labs).
- `npm run build` : build de production réussi (bundle ~80 Ko gzippé).
- Chaque interface TypeScript de `types/api.ts` comparée champ par champ aux
  réponses JSON réelles de l'API (via `TestClient`) pour tous les endpoints
  utilisés : écoles, compétences, cours, parcours, labs, leçons (avec
  sections/objectifs/niveaux de profondeur), quiz (avec options et corrigé).
- **Flux quiz complet simulé de bout en bout** exactement comme
  `QuizTakePage.tsx` l'exécute : chargement du quiz par compétence,
  construction du payload de réponses, soumission, vérification des champs
  du résultat retourné (score, `passed`, corrigé par question).
- **Flux lab complet simulé** : chargement public, soumission authentifiée,
  vérification de la confirmation.
- Champs de `PortfolioEvidence`, `CertificationListItem`, `CertificationDetail`,
  `CertificationRequirement`, `CertificationEligibility` et
  `RequirementEligibility` comparés un à un aux réponses JSON réelles.
- Champs de `AdminUser`, `AdminCourse`, `AdminLesson` (avec sections et
  niveaux de profondeur imbriqués) comparés un à un aux réponses JSON
  réelles des endpoints `/api/admin/*`.
- CORS vérifié en conditions réelles : requête `POST /api/auth/register`
  envoyée avec l'en-tête `Origin: http://localhost:5173` (origine du serveur
  Vite), réponse `201` avec `access-control-allow-origin` correct.
- Serveur de développement Vite démarré et testé (`HTTP 200` sur `/`) avant
  qu'une limite de cet environnement sandbox (les processus en arrière-plan
  ne survivent pas de manière fiable entre les appels d'outils) n'empêche un
  test interactif prolongé — voir limite ci-dessous.

### Limite connue de cet environnement de développement

Comme pour Docker, cet environnement ne permet pas de télécharger un
navigateur (Playwright/Chromium bloqué par la même restriction réseau que
Docker Hub) : impossible de prendre des captures d'écran réelles pour
l'auto-critique visuelle. La correction du CSS a été faite par relecture
attentive plutôt que par vérification visuelle — à confirmer au premier
lancement réel.
