"""add_imported_documents

Donne une identité au document importé, au-dessus de son arbre.

Deux raisons, l'une et l'autre décisives :

1. Le §45 place `source_file` en tête de ce qu'il faut conserver pour rendre
   un fragment citable. Sans le nom du document, « page 42 » ne veut rien
   dire. Il n'était stocké nulle part, sinon en texte libre dans la
   description du cours.

2. Un PDF peut désormais être importé comme simple document de référence,
   sans créer de cours. L'arbre devait donc pouvoir exister sans leçon, ce
   que `document_sections.lesson_id NOT NULL` interdisait.

`document_sections` change donc de rattachement : le document remplace la
leçon, et c'est le document qui porte le lien — facultatif — vers la leçon.

La bascule est faite sans reprise de données : ces tables ne sont écrites que
par le moteur d'import, dont aucun import n'avait encore eu lieu (vérifié :
0 ligne dans document_sections et content_blocks). Si des lignes existaient,
il faudrait leur créer un document d'accueil avant de rendre la colonne
obligatoire.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "imported_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_file", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        # SET NULL et non CASCADE : supprimer le cours dérivé ne doit pas
        # emporter le document du corpus.
        sa.Column("lesson_id", sa.String(), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_imported_documents_lesson", "imported_documents", ["lesson_id"])
    op.create_index("ix_imported_documents_school", "imported_documents", ["school_id"])

    # Les lignes existantes seraient orphelines : la table est vide, on les
    # écarte plutôt que d'inventer un document d'accueil (règle 8).
    op.execute("DELETE FROM document_sections")

    op.drop_index("ix_document_sections_lesson", table_name="document_sections")
    op.drop_column("document_sections", "lesson_id")
    op.add_column(
        "document_sections",
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("imported_documents.id", ondelete="CASCADE"), nullable=False,
        ),
    )
    op.create_index("ix_document_sections_document", "document_sections", ["document_id"])


def downgrade() -> None:
    op.execute("DELETE FROM document_sections")

    op.drop_index("ix_document_sections_document", table_name="document_sections")
    op.drop_column("document_sections", "document_id")
    op.add_column(
        "document_sections",
        sa.Column(
            "lesson_id", sa.String(),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False,
        ),
    )
    op.create_index("ix_document_sections_lesson", "document_sections", ["lesson_id"])

    op.drop_index("ix_imported_documents_school", table_name="imported_documents")
    op.drop_index("ix_imported_documents_lesson", table_name="imported_documents")
    op.drop_table("imported_documents")
