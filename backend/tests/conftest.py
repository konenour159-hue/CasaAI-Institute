"""
Socle de tests — connecte les tests à la vraie base Postgres utilisée par
l'application (celle de DATABASE_URL, cf. app/db/session.py) plutôt qu'une
base SQLite en mémoire : le schéma utilise des types Postgres spécifiques
(CITEXT sur `users.email`, énumérations natives) qu'une base de substitution
ne reproduirait pas fidèlement.

Chaque test tourne dans sa propre connexion + transaction externe, jamais
commitée : `join_transaction_mode="create_savepoint"` fait que les
`db.commit()` internes à l'application (AuthService, ProgressService...)
ne valident qu'un SAVEPOINT, jamais la transaction externe. Aucune donnée de
test ne persiste après le test, sans avoir à toucher au code applicatif ni à
préparer une base dédiée.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.db.session import engine, get_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _disable_rate_limiting() -> None:
    # Les tests appellent /api/auth/login et consorts bien plus souvent que
    # ne le permettent les limites réelles (cf. app/api/auth.py) — sans ça,
    # une suite de tests se ferait 429 elle-même.
    limiter.enabled = False


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
