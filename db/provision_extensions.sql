-- À exécuter UNE FOIS par un superuser PostgreSQL (ex: `postgres`), avant la
-- première migration Alembic. L'utilisateur applicatif (ex: `casa`) n'a pas
-- les droits pour créer des extensions — c'est un comportement PostgreSQL
-- normal, vérifié empiriquement lors de la mise en place de ce projet.
--
-- Usage :
--   psql -U postgres -d casa_dev -f db/provision_extensions.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS vector;
