"""
Engine SQLAlchemy et fabrique de sessions.

Ce module ne contient aucune logique métier — uniquement l'infrastructure
de connexion à PostgreSQL, réutilisée par toutes les routes FastAPI via la
dépendance `get_db`.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# `pool_pre_ping` évite de servir une connexion morte (utile derrière un
# reverse proxy / après une inactivité prolongée, cf. §6 CDC technique).
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI : ouvre une session par requête, la ferme toujours.

    Usage dans une route :
        @router.get("/courses")
        def list_courses(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
