"""add_document_structure

Ajoute document_sections et content_blocks : la structure hiérarchique
reconstruite par le moteur d'import PDF (option B de l'audit).

Ces tables s'ajoutent **à côté** de lesson_sections, qui n'est pas modifiée :
aucune leçon existante n'est touchée et l'affichage actuel continue de
fonctionner à l'identique. C'est ce qui distingue l'option B d'une migration
du modèle de contenu.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lesson_id", sa.String(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        # Auto-référence : l'imbrication que le modèle plat ne peut pas porter.
        sa.Column(
            "parent_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("level >= 1 AND level <= 4", name="ck_document_section_level"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_document_section_confidence"),
    )
    op.create_index("ix_document_sections_lesson", "document_sections", ["lesson_id"])
    op.create_index("ix_document_sections_parent", "document_sections", ["parent_id"])

    op.create_table(
        "content_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        # Chaîne plutôt qu'énumération native : TABLE et FORMULA arrivent aux
        # étapes suivantes, et un type énuméré PostgreSQL impose une migration
        # à chaque valeur ajoutée.
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False, server_default=""),
        sa.Column("items", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        # Provenance fine, socle de la traçabilité (§26) et du futur RAG (§45).
        sa.Column("source", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_content_block_confidence"),
    )
    op.create_index("ix_content_blocks_section", "content_blocks", ["section_id"])


def downgrade() -> None:
    # content_blocks d'abord : elle référence document_sections.
    op.drop_index("ix_content_blocks_section", table_name="content_blocks")
    op.drop_table("content_blocks")
    op.drop_index("ix_document_sections_parent", table_name="document_sections")
    op.drop_index("ix_document_sections_lesson", table_name="document_sections")
    op.drop_table("document_sections")
