"""
Endpoints admin — progression globale des apprenants (point 1 de
l'évolution ADMIN/SUPER_ADMIN : "Le Super Admin a accès à la progression
des users"). Réservées au rôle SUPER_ADMIN uniquement — un ADMIN simple,
restreint à la gestion de contenu, n'y a pas accès (cf. app/api/deps.py).

Ne couvre que les LEARNER : un ADMIN/SUPER_ADMIN n'a pas de progression
pédagogique à afficher ici par construction (Option B retenue : un super
admin qui veut suivre un cours utilise un second compte LEARNER séparé,
qui apparaît alors normalement dans cette liste comme n'importe quel
apprenant).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.session import get_db
from app.models.user import User
from app.repositories.admin_progress_repository import AdminProgressRepository
from app.schemas.admin import (
    AdminLearnerLabResultOut,
    AdminLearnerLessonProgressOut,
    AdminLearnerProgressDetailOut,
    AdminLearnerProgressListResponse,
    AdminLearnerProgressSummaryOut,
    AdminLearnerQuizAttemptOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin-progress"])


@router.get("/progress/learners", response_model=AdminLearnerProgressListResponse)
def list_learner_progress(
    search: str | None = Query(default=None, description="Recherche sur email/nom/prénom"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _super_admin: User = Depends(require_super_admin),
) -> AdminLearnerProgressListResponse:
    repo = AdminProgressRepository(db)
    learners, total = repo.list_learner_summaries(search=search, limit=limit, offset=offset)
    user_ids = [u.id for u in learners]

    lessons_total = repo.total_published_lessons()
    completed_by_user = repo.lessons_completed_counts(user_ids)
    quiz_by_user = repo.quiz_stats(user_ids)
    labs_by_user = repo.labs_completed_counts(user_ids)
    last_activity_by_user = repo.last_activity_at(user_ids)

    items = []
    for u in learners:
        attempted, passed, avg_score = quiz_by_user.get(u.id, (0, 0, None))
        items.append(
            AdminLearnerProgressSummaryOut(
                user_id=u.id, first_name=u.first_name, last_name=u.last_name, email=u.email,
                status=u.status,
                lessons_completed=completed_by_user.get(u.id, 0),
                lessons_total_published=lessons_total,
                quizzes_attempted=attempted,
                quizzes_passed=passed,
                quiz_average_score=avg_score,
                labs_completed=labs_by_user.get(u.id, 0),
                last_activity_at=last_activity_by_user.get(u.id),
            )
        )

    return AdminLearnerProgressListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/progress/learners/{user_id}", response_model=AdminLearnerProgressDetailOut)
def get_learner_progress_detail(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _super_admin: User = Depends(require_super_admin),
) -> AdminLearnerProgressDetailOut:
    repo = AdminProgressRepository(db)
    learner = repo.get_learner(user_id)
    if learner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apprenant introuvable (ou ce compte n'est pas un compte LEARNER).",
        )

    lessons = [
        AdminLearnerLessonProgressOut(
            lesson_id=lesson.id, lesson_title=lesson.title, course_id=lesson.course_id,
            status=progress.status, progress_pct=progress.progress_pct,
            started_at=progress.started_at, completed_at=progress.completed_at,
        )
        for progress, lesson in repo.list_lesson_progress(user_id)
    ]
    quiz_attempts = [
        AdminLearnerQuizAttemptOut(
            attempt_id=attempt.id, quiz_id=quiz.id, quiz_title=quiz.title,
            score=attempt.score, passed=attempt.passed,
            started_at=attempt.started_at, completed_at=attempt.completed_at,
        )
        for attempt, quiz in repo.list_quiz_attempts(user_id)
    ]
    lab_results = [
        AdminLearnerLabResultOut(
            result_id=result.id, lab_id=lab.id, lab_title=lab.title,
            mode=result.mode, completed=result.completed, score=result.score,
            submitted_at=result.submitted_at,
        )
        for result, lab in repo.list_lab_results(user_id)
    ]

    return AdminLearnerProgressDetailOut(
        user_id=learner.id, first_name=learner.first_name, last_name=learner.last_name,
        email=learner.email, status=learner.status,
        lessons=lessons, quiz_attempts=quiz_attempts, lab_results=lab_results,
    )
