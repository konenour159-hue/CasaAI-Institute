"""add_course_certificates

Ajoute la table course_certificates : certificat de module délivré
automatiquement quand la moyenne des meilleurs scores de quiz d'un cours
atteint le seuil (80 par défaut, cf. course_certificate_service.py).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("average_score", sa.SmallInteger(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "course_id", name="uq_user_course_certificate"),
    )


def downgrade() -> None:
    op.drop_table("course_certificates")
