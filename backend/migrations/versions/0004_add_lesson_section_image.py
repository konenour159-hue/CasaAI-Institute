"""add_lesson_section_image

Ajoute image_url et image_alt à lesson_sections : permet d'illustrer chaque
section de texte d'une leçon par une image (demande admin — formulaire
« Ajouter un cours », § éditeur de leçon). Colonnes nullable : aucune image
n'est requise, une section reste valide sans.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lesson_sections", sa.Column("image_url", sa.String(), nullable=True))
    op.add_column("lesson_sections", sa.Column("image_alt", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson_sections", "image_alt")
    op.drop_column("lesson_sections", "image_url")
