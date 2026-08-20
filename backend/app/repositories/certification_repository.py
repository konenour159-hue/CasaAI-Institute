from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.certification import Certification, CertificationRequirement, CourseCertificate
from app.models.content import Course, Lesson
from app.models.enums import ContentStatus, LessonProgressStatus, QuizKind
from app.models.progress import LabResult, QuizAttempt, UserLessonProgress, UserSkill
from app.models.quiz import Quiz


class CertificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_certifications(self) -> list[Certification]:
        return list(
            self.db.execute(
                select(Certification)
                .where(Certification.status == ContentStatus.PUBLISHED)
                .order_by(Certification.title)
            ).scalars()
        )

    def get_certification(self, certification_id: str) -> Certification | None:
        return self.db.execute(
            select(Certification)
            .options(selectinload(Certification.requirements))
            .where(Certification.id == certification_id, Certification.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none()

    # --- Signaux utilisés pour l'évaluation d'éligibilité -----------------

    def is_course_completed(self, user_id: uuid.UUID, course_id: str) -> bool:
        """Un cours est considéré terminé si toutes ses leçons publiées sont
        au statut COMPLETED pour cet utilisateur. Aucune notion de
        "complétion de cours" n'est stockée directement (seule la
        progression par leçon l'est) — c'est une dérivation, pas une donnée
        brute."""
        total_lessons = self.db.execute(
            select(func.count()).select_from(Lesson).where(
                Lesson.course_id == course_id, Lesson.status == ContentStatus.PUBLISHED
            )
        ).scalar_one()
        if total_lessons == 0:
            return False

        completed_lessons = self.db.execute(
            select(func.count()).select_from(UserLessonProgress).join(
                Lesson, Lesson.id == UserLessonProgress.lesson_id
            ).where(
                UserLessonProgress.user_id == user_id,
                Lesson.course_id == course_id,
                Lesson.status == ContentStatus.PUBLISHED,
                UserLessonProgress.status == LessonProgressStatus.COMPLETED,
            )
        ).scalar_one()
        return completed_lessons == total_lessons

    def is_lab_completed(self, user_id: uuid.UUID, lab_id: str) -> bool:
        return self.db.execute(
            select(LabResult.id).where(
                LabResult.user_id == user_id, LabResult.lab_id == lab_id, LabResult.completed.is_(True)
            )
        ).first() is not None

    def skill_mastery(self, user_id: uuid.UUID, skill_id: str) -> int:
        us = self.db.get(UserSkill, (user_id, skill_id))
        return us.mastery_level if us else 0

    # --- Certificat de module (par cours) ----------------------------------

    def course_exists_published(self, course_id: str) -> bool:
        return self.db.execute(
            select(Course.id).where(Course.id == course_id, Course.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none() is not None

    def list_course_quizzes(self, course_id: str) -> list[Quiz]:
        """Tous les quiz rattachés à un cours (§ certificat de module) :
        quiz final du cours, quiz de validation de ses leçons, et quiz de
        pratique des compétences enseignées par ses leçons — c'est ce dernier
        cas qui couvre la quasi-totalité des quiz existants aujourd'hui (le
        seed ne génère que des quiz PRACTICE, cf. scripts/seed.py)."""
        lesson_skill_ids = select(Lesson.skill_id).where(
            Lesson.course_id == course_id,
            Lesson.status == ContentStatus.PUBLISHED,
            Lesson.skill_id.isnot(None),
        )
        lesson_ids = select(Lesson.id).where(
            Lesson.course_id == course_id, Lesson.status == ContentStatus.PUBLISHED
        )
        return list(
            self.db.execute(
                select(Quiz)
                .where(
                    Quiz.status == ContentStatus.PUBLISHED,
                    (Quiz.course_id == course_id)
                    | (Quiz.lesson_id.in_(lesson_ids))
                    | ((Quiz.kind == QuizKind.PRACTICE) & Quiz.skill_id.in_(lesson_skill_ids)),
                )
                .order_by(Quiz.title)
            ).scalars().unique()
        )

    def best_score_for_quiz(self, user_id: uuid.UUID, quiz_id: uuid.UUID) -> int | None:
        return self.db.execute(
            select(func.max(QuizAttempt.score)).where(
                QuizAttempt.user_id == user_id, QuizAttempt.quiz_id == quiz_id
            )
        ).scalar_one_or_none()

    def get_course_certificate(self, user_id: uuid.UUID, course_id: str) -> CourseCertificate | None:
        return self.db.execute(
            select(CourseCertificate).where(
                CourseCertificate.user_id == user_id, CourseCertificate.course_id == course_id
            )
        ).scalar_one_or_none()

    def create_course_certificate(
        self, user_id: uuid.UUID, course_id: str, average_score: int
    ) -> CourseCertificate:
        cert = CourseCertificate(
            user_id=user_id, course_id=course_id, average_score=average_score,
            issued_at=datetime.now(timezone.utc),
        )
        self.db.add(cert)
        self.db.flush()
        return cert

    def list_my_course_certificates(self, user_id: uuid.UUID) -> list[CourseCertificate]:
        return list(
            self.db.execute(
                select(CourseCertificate)
                .where(CourseCertificate.user_id == user_id)
                .order_by(CourseCertificate.issued_at.desc())
            ).scalars()
        )
