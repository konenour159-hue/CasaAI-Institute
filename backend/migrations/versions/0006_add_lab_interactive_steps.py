"""add_lab_interactive_steps

Ajoute labs.interactive_steps (JSONB, nullable) : schéma interactif étape par
étape (pipeline de données, requête LLM...), rendu par un composant dédié
côté frontend quand présent. Refonte progressive des labos vers un format
interactif — premier sujet pilote : « pipeline d'une requête LLM ».

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("labs", sa.Column("interactive_steps", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("labs", "interactive_steps")
