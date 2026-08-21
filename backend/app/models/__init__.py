"""
Le simple fait d'importer chaque module de modèle ici garantit que toutes
les classes déclaratives sont enregistrées dans `Base.metadata` avant tout
appel à `Base.metadata.create_all()` ou à `alembic revision --autogenerate`.

Ordre d'import sans importance pour SQLAlchemy (contrairement au script SQL
brut) : les ForeignKey sont résolues par nom de table au moment du mapping,
pas au moment de l'exécution du fichier.
"""
from app.models.base import Base  # noqa: F401

from app.models import (  # noqa: F401
    user,
    catalog,
    content,
    document,
    lab,
    quiz,
    resource,
    knowledge,
    certification,
    progress,
    notification,
    ai,
)

__all__ = ["Base"]
