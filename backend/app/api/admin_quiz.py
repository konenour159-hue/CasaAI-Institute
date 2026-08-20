"""
Endpoints admin — gestion des quiz (§15 cahier fonctionnel). Réservés à
ADMIN et SUPER_ADMIN (require_content_admin), même périmètre que
cours/leçons (api/admin_content.py).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_content_admin
from app.db.session import get_db
from app.models.user import User
from app.repositories.admin_quiz_repository import AdminQuizRepository
from app.schemas.admin import AdminQuestionOut, AdminQuizIn, AdminQuizListResponse, AdminQuizOut
from app.services.admin_quiz_service import AdminQuizService, QuizNotFoundError, ValidationError

router = APIRouter(prefix="/api/admin/quizzes", tags=["admin-quiz"])


def _quiz_to_out(quiz, questions) -> AdminQuizOut:
    return AdminQuizOut(
        id=quiz.id, title=quiz.title, kind=quiz.kind, lesson_id=quiz.lesson_id, course_id=quiz.course_id,
        skill_id=quiz.skill_id, pass_threshold=quiz.pass_threshold, status=quiz.status,
        questions=[AdminQuestionOut.model_validate(q) for q in questions],
    )


@router.get("", response_model=AdminQuizListResponse)
def admin_list_quizzes(
    course_id: str | None = Query(default=None),
    lesson_id: str | None = Query(default=None),
    skill_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_content_admin),
) -> AdminQuizListResponse:
    rows, total = AdminQuizRepository(db).list_quizzes(
        course_id=course_id, lesson_id=lesson_id, skill_id=skill_id, limit=limit, offset=offset
    )
    return AdminQuizListResponse(
        items=[
            {
                "id": quiz.id, "title": quiz.title, "kind": quiz.kind, "lesson_id": quiz.lesson_id,
                "course_id": quiz.course_id, "skill_id": quiz.skill_id, "status": quiz.status,
                "question_count": count,
            }
            for quiz, count in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get("/{quiz_id}", response_model=AdminQuizOut)
def admin_get_quiz(
    quiz_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminQuizOut:
    repo = AdminQuizRepository(db)
    quiz = repo.get_quiz_any_status(quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    return _quiz_to_out(quiz, repo.get_quiz_questions(quiz_id))


@router.post("", response_model=AdminQuizOut, status_code=status.HTTP_201_CREATED)
def admin_create_quiz(
    payload: AdminQuizIn, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminQuizOut:
    try:
        quiz = AdminQuizService(db).create_quiz(payload)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return _quiz_to_out(quiz, AdminQuizRepository(db).get_quiz_questions(quiz.id))


@router.put("/{quiz_id}", response_model=AdminQuizOut)
def admin_update_quiz(
    quiz_id: uuid.UUID, payload: AdminQuizIn, db: Session = Depends(get_db),
    _admin: User = Depends(require_content_admin),
) -> AdminQuizOut:
    try:
        quiz = AdminQuizService(db).update_quiz(quiz_id, payload)
    except QuizNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return _quiz_to_out(quiz, AdminQuizRepository(db).get_quiz_questions(quiz.id))


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_quiz(
    quiz_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> None:
    try:
        AdminQuizService(db).delete_quiz(quiz_id)
    except QuizNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
