from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LessonProgressStatus


# --- Leçons (contenu complet, authentifié) -----------------------------------

class LessonSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    position: int
    title: str
    body: str
    image_url: str | None = None
    image_alt: str | None = None
    diagram: dict | None = None


class LessonDepthLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    depth_key: str
    label: str
    title: str
    body: str


class LessonDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    title: str
    level: str | None = None
    duration_min: int | None = None
    summary: str | None = None
    example: str | None = None
    position: int
    skill_id: str | None = None
    demo_id: str | None = None
    objectives: list[str] = []
    sections: list[LessonSectionOut] = []
    depth_levels: list[LessonDepthLevelOut] = []
    validation_quiz_id: str | None = None
    has_document: bool = False
    """Vrai si la leçon est issue d'un import PDF et dispose donc d'une
    structure documentaire reconstruite. Les leçons écrites à la main n'en
    ont pas : un booléen évite au client d'appeler pour rien."""


# --- Structure documentaire d'une leçon importée ----------------------------
# Le modèle plat rend le corps d'une section en un seul bloc de texte : listes,
# code, tableaux et formules y perdent leur nature. Ces schémas exposent
# l'arbre reconstruit à l'import, où chaque bloc a gardé la sienne.

class DocumentBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    text: str
    items: list | dict | None = None
    confidence: float
    page_start: int | None = None
    page_end: int | None = None


class DocumentSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    level: int
    confidence: float
    page_start: int | None = None
    page_end: int | None = None
    blocks: list[DocumentBlockOut] = []
    children: list["DocumentSectionOut"] = []


class LessonDocumentOut(BaseModel):
    source_file: str
    page_count: int
    sections: list[DocumentSectionOut] = []


class LessonCompleteResponse(BaseModel):
    lesson_id: str
    status: LessonProgressStatus
    progress_pct: int
    completed_at: datetime | None = None


class UserLessonProgressOut(BaseModel):
    lesson_id: str
    lesson_title: str
    course_id: str
    status: LessonProgressStatus
    progress_pct: int
    started_at: datetime | None = None
    completed_at: datetime | None = None


class UserSkillOut(BaseModel):
    skill_id: str
    skill_name: str
    school_id: str
    mastery_level: int
    updated_at: datetime


# --- Quiz -----------------------------------------------------------------

class QuizListItemOut(BaseModel):
    """Aperçu d'un quiz dans le catalogue global (GET /api/quizzes) — sans les
    questions, pour permettre de parcourir/découvrir tous les quiz existants
    sans devoir déjà connaître leur compétence ou leur cours d'origine."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    kind: str
    course_id: str | None = None
    lesson_id: str | None = None
    skill_id: str | None = None
    pass_threshold: int


class QuizOptionOut(BaseModel):
    """Jamais `is_correct` ici — l'apprenant ne doit pas voir la réponse
    avant d'avoir soumis sa tentative."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    position: int
    option_text: str


class QuizQuestionOut(BaseModel):
    id: str
    question_text: str
    options: list[QuizOptionOut]


class QuizOut(BaseModel):
    id: uuid.UUID
    title: str
    kind: str
    pass_threshold: int
    questions: list[QuizQuestionOut]


class QuizAnswerSubmission(BaseModel):
    question_id: str
    selected_option_id: uuid.UUID | None = None  # None = question laissée sans réponse


class QuizAttemptRequest(BaseModel):
    answers: list[QuizAnswerSubmission] = Field(min_length=1)


class QuizAnswerResultOut(BaseModel):
    question_id: str
    selected_option_id: uuid.UUID | None
    is_correct: bool
    correct_option_id: uuid.UUID
    explanation: str | None = None


class QuizAttemptResultOut(BaseModel):
    attempt_id: uuid.UUID
    score: int
    passed: bool
    correct_count: int
    total_questions: int
    answers: list[QuizAnswerResultOut]


class QuizAttemptHistoryOut(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    score: int
    passed: bool
    started_at: datetime
    completed_at: datetime | None = None


# --- Labs -----------------------------------------------------------------

class LabSubmitRequest(BaseModel):
    mode: str | None = None
    submission: dict | None = None
    score: int | None = Field(default=None, ge=0, le=100)


class LabResultOut(BaseModel):
    id: uuid.UUID
    lab_id: str
    mode: str | None = None
    completed: bool
    score: int | None = None
    feedback: str | None = None
    submitted_at: datetime | None = None
