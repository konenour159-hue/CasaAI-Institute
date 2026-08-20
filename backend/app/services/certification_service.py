"""
Évaluation d'éligibilité à une certification (§18 cahier fonctionnel : « le
système détermine si l'apprenant satisfait les conditions »).

Honnêteté délibérée : seuls les critères objectivement vérifiables à partir
des données stockées sont évalués automatiquement (cours terminé, lab
complété, compétence atteignant un seuil de maîtrise, score minimum quand
lié à une compétence précise). Les critères de type EVIDENCE ou
FINAL_PROJECT — et les MIN_SCORE sans compétence associée, cas de la
quasi-totalité des critères hérités du prototype (texte libre non structuré,
cf. scripts/seed.py) — ne peuvent pas être vérifiés par un script et
restent `satisfied: null`, en attente d'une revue humaine.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CertificationRequirementType
from app.repositories.certification_repository import CertificationRepository
from app.schemas.certification import CertificationEligibilityOut, RequirementEligibilityOut

# Seuil de maîtrise (sur 4) considéré suffisant pour satisfaire un critère
# de type SKILL. Choix V1 volontairement simple, à ajuster si besoin.
SKILL_MASTERY_THRESHOLD = 2


def _best_quiz_score_for_skill(db: Session, user_id: uuid.UUID, skill_id: str) -> int | None:
    """Pour un MIN_SCORE lié à une compétence : meilleur score atteint par
    une tentative de son quiz de pratique."""
    from app.models.progress import QuizAttempt
    from app.models.quiz import Quiz

    return db.execute(
        select(QuizAttempt.score)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(QuizAttempt.user_id == user_id, Quiz.skill_id == skill_id)
        .order_by(QuizAttempt.score.desc())
        .limit(1)
    ).scalar_one_or_none()


class CertificationService:
    def __init__(self, db: Session):
        self.db = db
        self.cert_repo = CertificationRepository(db)

    def evaluate_eligibility(self, user_id: uuid.UUID, certification_id: str) -> CertificationEligibilityOut | None:
        certification = self.cert_repo.get_certification(certification_id)
        if certification is None:
            return None

        results: list[RequirementEligibilityOut] = []
        for req in certification.requirements:
            satisfied, detail = self._evaluate_one(user_id, req)
            results.append(RequirementEligibilityOut(
                requirement_id=str(req.id), requirement_type=req.requirement_type.value,
                description=req.description, satisfied=satisfied, detail=detail,
            ))

        eligible = len(results) > 0 and all(r.satisfied is True for r in results)
        return CertificationEligibilityOut(
            certification_id=certification_id, eligible=eligible, requirements=results,
        )

    def _evaluate_one(self, user_id: uuid.UUID, req) -> tuple[bool | None, str]:
        rtype = req.requirement_type

        if rtype == CertificationRequirementType.COURSE and req.course_id:
            ok = self.cert_repo.is_course_completed(user_id, req.course_id)
            return ok, f"Cours '{req.course_id}' " + ("terminé." if ok else "non terminé.")

        if rtype == CertificationRequirementType.LAB and req.lab_id:
            ok = self.cert_repo.is_lab_completed(user_id, req.lab_id)
            return ok, f"Lab '{req.lab_id}' " + ("complété." if ok else "non complété.")

        if rtype == CertificationRequirementType.SKILL and req.skill_id:
            level = self.cert_repo.skill_mastery(user_id, req.skill_id)
            ok = level >= SKILL_MASTERY_THRESHOLD
            return ok, f"Maîtrise de '{req.skill_id}' : {level}/4 (seuil requis : {SKILL_MASTERY_THRESHOLD}/4)."

        if rtype == CertificationRequirementType.MIN_SCORE and req.skill_id and req.min_score is not None:
            best = _best_quiz_score_for_skill(self.db, user_id, req.skill_id)
            ok = best is not None and best >= req.min_score
            return ok, (
                f"Meilleur score sur '{req.skill_id}' : {best if best is not None else 'aucune tentative'}"
                f" (seuil requis : {req.min_score})."
            )

        # EVIDENCE, FINAL_PROJECT, ou MIN_SCORE/SKILL/COURSE/LAB sans
        # référence structurée (cas de la quasi-totalité des critères hérités
        # du prototype) : non vérifiable automatiquement.
        return None, "Nécessite une revue manuelle (critère non structuré ou preuve à évaluer par un administrateur)."
