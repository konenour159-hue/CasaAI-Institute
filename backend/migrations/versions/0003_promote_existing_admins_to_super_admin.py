"""promote_existing_admins_to_super_admin

Politique de migration : tous les comptes ADMIN existants au moment de
cette migration sont promus en SUPER_ADMIN, afin que personne ne perde
d'accès silencieusement lors de l'introduction de la distinction
ADMIN / SUPER_ADMIN.

C'est ensuite au(x) super admin(s) de redescendre manuellement certains
comptes en ADMIN simple, via `PATCH /api/admin/users/{id}` (rôle réservé
à SUPER_ADMIN), une fois qu'on sait qui doit garder l'accès complet
(utilisateurs, progression globale, certifications) et qui doit être
restreint à la gestion de contenu (cours/leçons/import PDF).

Rappel des périmètres (voir app/api/deps.py) :
  - ADMIN       : cours, leçons, import PDF.
  - SUPER_ADMIN : sur-ensemble d'ADMIN + utilisateurs (dont suppression),
                  progression globale, certifications. Ne participe pas
                  aux cours en tant qu'apprenant (convention d'usage :
                  compte LEARNER séparé si besoin, pas de blocage
                  applicatif dédié).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'SUPER_ADMIN' WHERE role = 'ADMIN';")


def downgrade() -> None:
    # Redescend tout SUPER_ADMIN en ADMIN. Perd l'information de qui était
    # "vraiment" super admin avant la promotion automatique de l'upgrade —
    # c'est attendu : le downgrade ramène au modèle à un seul rôle
    # privilégié (0001), où cette distinction n'existait pas.
    op.execute("UPDATE users SET role = 'ADMIN' WHERE role = 'SUPER_ADMIN';")
