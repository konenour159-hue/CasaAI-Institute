"""
Certificat de module (par cours), basé uniquement sur les scores de quiz —
demande produit : « lister tous les quiz et, si la moyenne de l'apprenant
dépasse 80%, délivrer un certificat sur le module ». Volontairement séparé
du catalogue `Certification` (parcours multi-cours à critères définis par un
administrateur, cf. certification_service.py) : ici l'éligibilité est
entièrement automatique, dérivée des tentatives de quiz d'un seul cours.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.certification import CourseCertificate
from app.repositories.certification_repository import CertificationRepository
from app.schemas.certification import CourseCertificateEligibilityOut, CourseQuizScoreOut

# Seuil de réussite du module, en pourcentage de la moyenne des meilleurs
# scores obtenus sur chaque quiz du cours.
COURSE_CERTIFICATE_THRESHOLD = 80


class CourseNotFoundError(Exception):
    pass


class NotEligibleError(Exception):
    """L'apprenant n'a pas encore atteint le seuil requis (ou n'a pas tenté
    tous les quiz du cours) — le certificat ne peut pas être délivré."""


class CourseCertificateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CertificationRepository(db)

    def get_eligibility(self, user_id: uuid.UUID, course_id: str) -> CourseCertificateEligibilityOut:
        if not self.repo.course_exists_published(course_id):
            raise CourseNotFoundError(f"Cours '{course_id}' introuvable.")

        quizzes = self.repo.list_course_quizzes(course_id)
        quiz_scores: list[CourseQuizScoreOut] = []
        attempted_scores: list[int] = []
        for quiz in quizzes:
            best = self.repo.best_score_for_quiz(user_id, quiz.id)
            quiz_scores.append(CourseQuizScoreOut(
                quiz_id=quiz.id, quiz_title=quiz.title, kind=quiz.kind.value,
                best_score=best, attempted=best is not None,
            ))
            if best is not None:
                attempted_scores.append(best)

        all_attempted = len(quizzes) > 0 and len(attempted_scores) == len(quizzes)
        average = round(sum(attempted_scores) / len(attempted_scores), 1) if attempted_scores else None
        eligible = all_attempted and average is not None and average >= COURSE_CERTIFICATE_THRESHOLD

        existing = self.repo.get_course_certificate(user_id, course_id)
        return CourseCertificateEligibilityOut(
            course_id=course_id, threshold=COURSE_CERTIFICATE_THRESHOLD, quizzes=quiz_scores,
            all_attempted=all_attempted, average_score=average, eligible=eligible,
            already_issued=existing is not None, issued_at=existing.issued_at if existing else None,
        )

    def issue_certificate(self, user_id: uuid.UUID, course_id: str) -> CourseCertificate:
        existing = self.repo.get_course_certificate(user_id, course_id)
        if existing is not None:
            return existing

        eligibility = self.get_eligibility(user_id, course_id)
        if not eligibility.eligible:
            if not eligibility.quizzes:
                raise NotEligibleError("Aucun quiz n'est encore rattaché à ce cours.")
            if not eligibility.all_attempted:
                remaining = [q.quiz_title for q in eligibility.quizzes if not q.attempted]
                raise NotEligibleError(
                    f"Tous les quiz du cours doivent être tentés au moins une fois "
                    f"(reste : {', '.join(remaining)})."
                )
            raise NotEligibleError(
                f"Moyenne actuelle : {eligibility.average_score} (seuil requis : {COURSE_CERTIFICATE_THRESHOLD})."
            )

        cert = self.repo.create_course_certificate(
            user_id, course_id, average_score=round(eligibility.average_score)
        )
        self.db.commit()
        self.db.refresh(cert)
        return cert
