"""add_section_diagram_and_resource_url

Ajoute lesson_sections.diagram (JSONB, nullable) : petit schéma statique
rendu par <MiniDiagram> côté frontend, pour les sections qui décrivent une
relation/comparaison/processus. Ajoute resources.url (nullable) : lien
cliquable requis pour une bibliographie de fin de cours (resources/
resource_courses existaient déjà mais n'étaient reliés à rien côté API/
frontend).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lesson_sections", sa.Column("diagram", postgresql.JSONB(), nullable=True))
    op.add_column("resources", sa.Column("url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("resources", "url")
    op.drop_column("lesson_sections", "diagram")
