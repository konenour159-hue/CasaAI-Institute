"""
Édition des critères de certification (SUPER_ADMIN — §periметre certifications,
cf. app/api/deps.py). Valide la cohérence type ↔ référence avant d'écrire,
même philosophie que AdminQuizService pour les quiz : un critère MIN_SCORE ou
SKILL sans skill_id, ou COURSE sans course_id, ou LAB sans lab_id, resterait
silencieusement non vérifiable par CertificationService — on préfère le
signaler explicitement à la saisie.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.certification import CertificationRequirement
from app.models.enums import CertificationRequirementType
from app.repositories.admin_certification_repository import AdminCertificationRepository
from app.schemas.admin import AdminCertificationRequirementIn

_REQUIRES_REFERENCE = {
    CertificationRequirementType.COURSE: "course_id",
    CertificationRequirementType.LAB: "lab_id",
    CertificationRequirementType.SKILL: "skill_id",
    CertificationRequirementType.MIN_SCORE: "skill_id",
}


class ValidationError(Exception):
    pass


class CertificationNotFoundError(Exception):
    pass


class RequirementNotFoundError(Exception):
    pass


class AdminCertificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminCertificationRepository(db)

    def update_requirement(
        self, certification_id: str, requirement_id: uuid.UUID, data: AdminCertificationRequirementIn
    ) -> CertificationRequirement:
        if self.repo.get_certification_any_status(certification_id) is None:
            raise CertificationNotFoundError(f"Certification '{certification_id}' introuvable.")

        requirement = self.repo.get_requirement(certification_id, requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Critère '{requirement_id}' introuvable pour cette certification.")

        self._validate(data)
        requirement = self.repo.update_requirement(requirement, data)
        self.db.commit()
        self.db.refresh(requirement)
        return requirement

    def _validate(self, data: AdminCertificationRequirementIn) -> None:
        if data.skill_id and not self.repo.skill_exists(data.skill_id):
            raise ValidationError(f"Compétence '{data.skill_id}' introuvable.")
        if data.course_id and not self.repo.course_exists(data.course_id):
            raise ValidationError(f"Cours '{data.course_id}' introuvable.")
        if data.lab_id and not self.repo.lab_exists(data.lab_id):
            raise ValidationError(f"Lab '{data.lab_id}' introuvable.")

        expected_field = _REQUIRES_REFERENCE.get(data.requirement_type)
        if expected_field == "skill_id" and not data.skill_id:
            label = "MIN_SCORE" if data.requirement_type == CertificationRequirementType.MIN_SCORE else "SKILL"
            raise ValidationError(f"Un critère de type {label} doit référencer une compétence.")
        if expected_field == "course_id" and not data.course_id:
            raise ValidationError("Un critère de type COURSE doit référencer un cours.")
        if expected_field == "lab_id" and not data.lab_id:
            raise ValidationError("Un critère de type LAB doit référencer un lab.")

        if data.requirement_type == CertificationRequirementType.MIN_SCORE and data.min_score is None:
            raise ValidationError("Un critère de type MIN_SCORE doit préciser un score minimum.")
