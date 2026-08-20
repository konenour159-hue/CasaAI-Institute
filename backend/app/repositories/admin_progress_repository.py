"""
Requêtes de progression agrégée pour la vue SUPER_ADMIN (§ point 1 de
l'évolution ADMIN/SUPER_ADMIN — dashboard de progression globale des
apprenants). Distinct de ProgressRepository (app/repositories/progress_repository.py)
qui sert les routes `/me/*` d'un utilisateur sur sa propre progression :
ici, les requêtes portent sur l'ensemble des LEARNER, ou sur un LEARNER
ciblé par un admin.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.content import Lesson
from app.models.enums import ContentStatus, LessonProgressStatus, UserRole
from app.models.lab import Lab
from app.models.progress import LabResult, QuizAttempt, UserLessonProgress
from app.models.quiz import Quiz
from app.models.user import User


class AdminProgressRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Vue liste : un résumé de progression par apprenant --------------

    def list_learner_summaries(
        self, *, search: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[User], int]:
        """Réutilise le même filtre de recherche que UserRepository.list_all,
        mais restreint volontairement aux LEARNER : un ADMIN/SUPER_ADMIN n'a
        pas de progression pédagogique à afficher ici (cf. Option B — un
        super admin qui veut suivre un cours utilise un compte LEARNER
        séparé, donc ce compte-là apparaîtra normalement dans cette liste)."""
        stmt = select(User).where(User.role == UserRole.LEARNER)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(User.email.ilike(pattern), User.first_name.ilike(pattern), User.last_name.ilike(pattern))
            )
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            self.db.execute(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def total_published_lessons(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(Lesson).where(Lesson.status == ContentStatus.PUBLISHED)
        ).scalar_one()

    def lessons_completed_counts(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not user_ids:
            return {}
        rows = self.db.execute(
            select(UserLessonProgress.user_id, func.count())
            .where(
                UserLessonProgress.user_id.in_(user_ids),
                UserLessonProgress.status == LessonProgressStatus.COMPLETED,
            )
            .group_by(UserLessonProgress.user_id)
        ).all()
        return {uid: count for uid, count in rows}

    def quiz_stats(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int, float | None]]:
        """Renvoie {user_id: (nb_tentatives, nb_reussies, score_moyen)}."""
        if not user_ids:
            return {}
        totals_and_avg = self.db.execute(
            select(QuizAttempt.user_id, func.count(), func.avg(QuizAttempt.score))
            .where(QuizAttempt.user_id.in_(user_ids))
            .group_by(QuizAttempt.user_id)
        ).all()
        passed_rows = self.db.execute(
            select(QuizAttempt.user_id, func.count())
            .where(QuizAttempt.user_id.in_(user_ids), QuizAttempt.passed.is_(True))
            .group_by(QuizAttempt.user_id)
        ).all()
        passed_by_user = {uid: count for uid, count in passed_rows}

        result: dict[uuid.UUID, tuple[int, int, float | None]] = {}
        for uid, total_attempts, avg_score in totals_and_avg:
            result[uid] = (total_attempts, passed_by_user.get(uid, 0), float(avg_score) if avg_score is not None else None)
        return result

    def labs_completed_counts(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not user_ids:
            return {}
        rows = self.db.execute(
            select(LabResult.user_id, func.count())
            .where(LabResult.user_id.in_(user_ids), LabResult.completed.is_(True))
            .group_by(LabResult.user_id)
        ).all()
        return {uid: count for uid, count in rows}

    def last_activity_at(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, object]:
        """Dernière activité connue par apprenant : max(updated_at) sur la
        progression de leçon. Signal simple et suffisant pour un dashboard ;
        on pourrait plus tard croiser avec quiz/labs si besoin d'une
        granularité plus fine."""
        if not user_ids:
            return {}
        rows = self.db.execute(
            select(UserLessonProgress.user_id, func.max(UserLessonProgress.updated_at))
            .where(UserLessonProgress.user_id.in_(user_ids))
            .group_by(UserLessonProgress.user_id)
        ).all()
        return {uid: ts for uid, ts in rows}

    # --- Vue détail : progression complète d'un apprenant précis ---------

    def get_learner(self, user_id: uuid.UUID) -> User | None:
        user = self.db.get(User, user_id)
        if user is None or user.role != UserRole.LEARNER:
            return None
        return user

    def list_lesson_progress(self, user_id: uuid.UUID) -> list[tuple[UserLessonProgress, Lesson]]:
        rows = self.db.execute(
            select(UserLessonProgress, Lesson)
            .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
            .where(UserLessonProgress.user_id == user_id)
            .order_by(UserLessonProgress.updated_at.desc())
        ).all()
        return [(p, l) for p, l in rows]

    def list_quiz_attempts(self, user_id: uuid.UUID) -> list[tuple[QuizAttempt, Quiz]]:
        rows = self.db.execute(
            select(QuizAttempt, Quiz)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.started_at.desc())
        ).all()
        return [(a, q) for a, q in rows]

    def list_lab_results(self, user_id: uuid.UUID) -> list[tuple[LabResult, Lab]]:
        rows = self.db.execute(
            select(LabResult, Lab)
            .join(Lab, Lab.id == LabResult.lab_id)
            .where(LabResult.user_id == user_id)
            .order_by(LabResult.submitted_at.desc())
        ).all()
        return [(r, l) for r, l in rows]
