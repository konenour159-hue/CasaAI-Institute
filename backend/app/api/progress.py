"""
Endpoints de progression apprenant (§15/§16/§14 cahier fonctionnel ; §5 API
"Progression"/"Quiz"/"Labs" du cahier technique). Tous authentifiés.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.progress_repository import ProgressRepository
from app.repositories.document_structure_repository import DocumentStructureRepository
from app.schemas.progress import (
    DocumentBlockOut,
    DocumentSectionOut,
    LabResultOut,
    LabSubmitRequest,
    LessonCompleteResponse,
    LessonDetailOut,
    LessonDocumentOut,
    QuizAttemptHistoryOut,
    QuizAttemptRequest,
    QuizAttemptResultOut,
    QuizListItemOut,
    QuizOptionOut,
    QuizOut,
    QuizQuestionOut,
    UserLessonProgressOut,
    UserSkillOut,
)
from app.services.progress_service import ProgressService, QuizNotFoundError, UnknownQuestionError

router = APIRouter(prefix="/api", tags=["progress"])


# --- Leçons -----------------------------------------------------------

@router.get("/lessons/{lesson_id}", response_model=LessonDetailOut)
def get_lesson(
    lesson_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LessonDetailOut:
    repo = ProgressRepository(db)
    lesson = repo.get_lesson_detail(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leçon introuvable.")
    return LessonDetailOut(
        id=lesson.id, course_id=lesson.course_id, title=lesson.title, level=lesson.level,
        duration_min=lesson.duration_min, summary=lesson.summary, example=lesson.example,
        position=lesson.position, skill_id=lesson.skill_id, demo_id=lesson.demo_id,
        objectives=[o.label for o in lesson.objectives],
        sections=lesson.sections, depth_levels=lesson.depth_levels,
        validation_quiz_id=repo.get_validation_quiz_id(lesson_id),
        has_document=DocumentStructureRepository(db).get_document_for_lesson(lesson_id) is not None,
    )


def _document_section(section) -> DocumentSectionOut:
    return DocumentSectionOut(
        title=section.title, level=section.level, confidence=section.confidence,
        page_start=section.page_start, page_end=section.page_end,
        blocks=[DocumentBlockOut.model_validate(block) for block in section.blocks],
        children=[_document_section(child) for child in section.children],
    )


@router.get("/lessons/{lesson_id}/document", response_model=LessonDocumentOut)
def get_lesson_document(
    lesson_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LessonDocumentOut:
    """Structure documentaire d'une leçon issue d'un import PDF.

    Servie à part du détail de leçon plutôt qu'incluse dedans : les leçons
    écrites à la main n'en ont aucune, et l'arbre d'un ouvrage entier n'a rien
    à faire dans une réponse que tout le monde demande. `has_document` sur le
    détail dit s'il vaut la peine d'appeler.
    """
    if ProgressRepository(db).get_lesson_detail(lesson_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leçon introuvable.")

    structure = DocumentStructureRepository(db)
    document = structure.get_document_for_lesson(lesson_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cette leçon n'est pas issue d'un import : elle n'a pas de structure documentaire.",
        )

    return LessonDocumentOut(
        source_file=document.source_file, page_count=document.page_count,
        sections=[_document_section(root) for root in structure.get_tree(document.id)],
    )


@router.post("/lessons/{lesson_id}/complete", response_model=LessonCompleteResponse)
def complete_lesson(
    lesson_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LessonCompleteResponse:
    # Vérifie que la leçon existe et est publiée avant d'enregistrer une
    # progression dessus (évite de créer un enregistrement orphelin).
    if ProgressRepository(db).get_lesson_detail(lesson_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leçon introuvable.")

    progress = ProgressService(db).complete_lesson(current_user.id, lesson_id)
    return LessonCompleteResponse(
        lesson_id=lesson_id, status=progress.status,
        progress_pct=progress.progress_pct, completed_at=progress.completed_at,
    )


@router.get("/me/progress", response_model=list[UserLessonProgressOut])
def get_my_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserLessonProgressOut]:
    rows = ProgressRepository(db).list_user_progress(current_user.id)
    return [
        UserLessonProgressOut(
            lesson_id=lesson.id, lesson_title=lesson.title, course_id=lesson.course_id,
            status=progress.status, progress_pct=progress.progress_pct,
            started_at=progress.started_at, completed_at=progress.completed_at,
        )
        for progress, lesson in rows
    ]


@router.get("/me/skills", response_model=list[UserSkillOut])
def get_my_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserSkillOut]:
    rows = ProgressRepository(db).list_user_skills(current_user.id)
    return [
        UserSkillOut(
            skill_id=skill.id, skill_name=skill.name, school_id=skill.school_id,
            mastery_level=us.mastery_level, updated_at=us.updated_at,
        )
        for us, skill in rows
    ]


# --- Quiz -----------------------------------------------------------

@router.get("/quizzes", response_model=list[QuizListItemOut])
def list_quizzes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QuizListItemOut]:
    """Catalogue complet des quiz publiés, toutes natures confondues
    (entraînement par compétence, validation de leçon, final de cours) —
    permet de les découvrir sans passer par une leçon/compétence précise."""
    quizzes = ProgressRepository(db).list_all_quizzes()
    return [QuizListItemOut.model_validate(q) for q in quizzes]


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
def get_quiz(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuizOut:
    result = ProgressRepository(db).get_quiz_with_questions(quiz_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    quiz, questions_with_options = result
    return QuizOut(
        id=quiz.id, title=quiz.title, kind=quiz.kind.value, pass_threshold=quiz.pass_threshold,
        questions=[
            QuizQuestionOut(
                id=q.id, question_text=q.question_text,
                options=[QuizOptionOut.model_validate(o) for o in options],
            )
            for q, options in questions_with_options
        ],
    )


@router.get("/skills/{skill_id}/quiz", response_model=QuizOut)
def get_practice_quiz_for_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuizOut:
    """Retrouve le quiz d'entraînement associé à une compétence, sans que le
    frontend ait besoin de connaître son UUID à l'avance."""
    result = ProgressRepository(db).get_practice_quiz_by_skill(skill_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Aucun quiz d'entraînement pour cette compétence."
        )
    quiz, questions_with_options = result
    return QuizOut(
        id=quiz.id, title=quiz.title, kind=quiz.kind.value, pass_threshold=quiz.pass_threshold,
        questions=[
            QuizQuestionOut(
                id=q.id, question_text=q.question_text,
                options=[QuizOptionOut.model_validate(o) for o in options],
            )
            for q, options in questions_with_options
        ],
    )


@router.post("/quizzes/{quiz_id}/attempt", response_model=QuizAttemptResultOut)
def attempt_quiz(
    quiz_id: uuid.UUID,
    payload: QuizAttemptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuizAttemptResultOut:
    service = ProgressService(db)
    try:
        return service.submit_quiz_attempt(user_id=current_user.id, quiz_id=quiz_id, payload=payload)
    except QuizNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnknownQuestionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


@router.get("/me/quiz-history", response_model=list[QuizAttemptHistoryOut])
def get_my_quiz_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QuizAttemptHistoryOut]:
    rows = ProgressRepository(db).list_quiz_history(current_user.id)
    return [
        QuizAttemptHistoryOut(
            attempt_id=attempt.id, quiz_id=quiz.id, quiz_title=quiz.title,
            score=attempt.score, passed=attempt.passed,
            started_at=attempt.started_at, completed_at=attempt.completed_at,
        )
        for attempt, quiz in rows
    ]


# --- Labs -----------------------------------------------------------

@router.post("/labs/{lab_id}/submit", response_model=LabResultOut)
def submit_lab(
    lab_id: str,
    payload: LabSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LabResultOut:
    result = ProgressService(db).submit_lab(
        user_id=current_user.id, lab_id=lab_id, mode=payload.mode,
        submission=payload.submission, score=payload.score,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab introuvable.")
    return result


@router.get("/me/lab-results", response_model=list[LabResultOut])
def get_my_lab_results(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LabResultOut]:
    return ProgressRepository(db).list_lab_results(current_user.id)
