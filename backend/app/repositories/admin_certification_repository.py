"""
Accès en écriture aux critères de certification (SUPER_ADMIN uniquement, cf.
api/admin_certifications.py). Le catalogue de certifications lui-même
(Certification) et la structure de ses critères (CertificationRequirement)
sont créés par le seed depuis le texte libre du prototype ; ce repository ne
gère que l'édition des critères déjà existants — attacher une référence
structurée (skill/course/lab) et un seuil, pas la création de nouveaux
critères ou de nouvelles certifications (hors périmètre demandé).
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Skill
from app.models.certification import Certification, CertificationRequirement
from app.models.content import Course
from app.models.lab import Lab
from app.schemas.admin import AdminCertificationRequirementIn


class AdminCertificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_certifications(self) -> list[tuple[Certification, int, int]]:
        """Renvoie (certification, nombre de critères, nombre de critères
        déjà reliés à une référence structurée) — sert d'indicateur de
        complétion dans la liste admin."""
        certs = list(self.db.execute(select(Certification).order_by(Certification.title)).scalars())
        rows = self.db.execute(
            select(
                CertificationRequirement.certification_id,
                func.count(),
                func.count(CertificationRequirement.skill_id)
                + func.count(CertificationRequirement.course_id)
                + func.count(CertificationRequirement.lab_id),
            ).group_by(CertificationRequirement.certification_id)
        ).all()
        counts = {cert_id: (total, linked) for cert_id, total, linked in rows}
        return [(c, *counts.get(c.id, (0, 0))) for c in certs]

    def get_certification_any_status(self, certification_id: str) -> Certification | None:
        return self.db.execute(
            select(Certification)
            .options(selectinload(Certification.requirements))
            .where(Certification.id == certification_id)
        ).scalar_one_or_none()

    def get_requirement(self, certification_id: str, requirement_id: uuid.UUID) -> CertificationRequirement | None:
        return self.db.execute(
            select(CertificationRequirement).where(
                CertificationRequirement.id == requirement_id,
                CertificationRequirement.certification_id == certification_id,
            )
        ).scalar_one_or_none()

    def skill_exists(self, skill_id: str) -> bool:
        return self.db.get(Skill, skill_id) is not None

    def course_exists(self, course_id: str) -> bool:
        return self.db.get(Course, course_id) is not None

    def lab_exists(self, lab_id: str) -> bool:
        return self.db.get(Lab, lab_id) is not None

    def update_requirement(
        self, requirement: CertificationRequirement, data: AdminCertificationRequirementIn
    ) -> CertificationRequirement:
        requirement.requirement_type = data.requirement_type
        requirement.description = data.description
        requirement.course_id = data.course_id
        requirement.lab_id = data.lab_id
        requirement.skill_id = data.skill_id
        requirement.min_score = data.min_score
        self.db.flush()
        return requirement
