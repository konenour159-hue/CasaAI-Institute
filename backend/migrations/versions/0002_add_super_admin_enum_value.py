"""add_super_admin_enum_value

Ajoute la valeur SUPER_ADMIN au type Postgres user_role.

Volontairement séparée de la migration 0003 (qui promeut les admins
existants) : PostgreSQL interdit d'utiliser une valeur d'ENUM tout juste
ajoutée par `ALTER TYPE ... ADD VALUE` dans la même transaction qui l'a
ajoutée. Alembic exécutant chaque migration dans sa propre transaction,
il faut deux révisions distinctes pour que la seconde puisse réellement
utiliser 'SUPER_ADMIN' dans un UPDATE.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'SUPER_ADMIN';")


def downgrade() -> None:
    # LIMITATION CONNUE ET ASSUMÉE : PostgreSQL ne permet pas de retirer une
    # valeur d'un type ENUM sans le recréer entièrement (renommer l'ancien
    # type, en créer un nouveau sans la valeur, migrer la colonne, supprimer
    # l'ancien type). Ce downgrade ne le fait PAS automatiquement : c'est
    # une opération destructive qui doit être conduite manuellement, en
    # s'assurant d'abord (via la migration 0003 downgrade) qu'aucune ligne
    # n'utilise plus 'SUPER_ADMIN'. Le downgrade se contente donc ici de ne
    # rien faire — la valeur 'SUPER_ADMIN' reste présente dans le type mais
    # inutilisée après le downgrade de 0003.
    pass
