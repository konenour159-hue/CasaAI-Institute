from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CertificationListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    level: str | None = None
    description: str | None = None
    color: str | None = None


class CertificationRequirementOut(BaseModel):
    id: str
    requirement_type: str
    description: str | None = None
    course_id: str | None = None
    lab_id: str | None = None
    skill_id: str | None = None
    min_score: int | None = None


class CertificationDetailOut(CertificationListOut):
    requirements: list[CertificationRequirementOut] = []


class RequirementEligibilityOut(BaseModel):
    requirement_id: str
    requirement_type: str
    description: str | None = None
    satisfied: bool | None
    """None = non vérifiable automatiquement avec les données actuelles
    (ex: critère EVIDENCE en texte libre, ou MIN_SCORE sans compétence
    associée) — nécessite une revue manuelle par un administrateur."""
    detail: str


class CertificationEligibilityOut(BaseModel):
    certification_id: str
    eligible: bool
    """True seulement si TOUS les critères sont automatiquement vérifiés et
    satisfaits. Un seul critère non vérifiable (`satisfied: null`) empêche
    l'éligibilité automatique, même si tout le reste est acquis — reflet
    honnête des limites actuelles des données de certification (la plupart
    des critères hérités du prototype sont en texte libre non structuré)."""
    requirements: list[RequirementEligibilityOut]


# --- Certificat de module (par cours, basé sur les quiz) -------------------

class CourseQuizScoreOut(BaseModel):
    quiz_id: uuid.UUID
    quiz_title: str
    kind: str
    best_score: int | None
    attempted: bool


class CourseCertificateEligibilityOut(BaseModel):
    course_id: str
    threshold: int
    quizzes: list[CourseQuizScoreOut]
    all_attempted: bool
    """False s'il n'y a aucun quiz pour ce cours, ou si au moins un quiz du
    cours n'a pas encore été tenté par l'apprenant."""
    average_score: float | None
    """Moyenne des meilleurs scores obtenus sur chaque quiz du cours. `None`
    tant qu'aucune tentative n'a été faite."""
    eligible: bool
    already_issued: bool
    issued_at: datetime | None = None


class CourseCertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: str
    average_score: int
    issued_at: datetime
