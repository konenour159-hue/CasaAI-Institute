from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AccountStatus,
    CertificationRequirementType,
    ContentStatus,
    LessonDepthKey,
    LessonProgressStatus,
    QuizKind,
    UserRole,
)


# --- Utilisateurs -----------------------------------------------------------

class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    role: UserRole
    status: AccountStatus
    created_at: datetime
    last_login_at: datetime | None = None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserOut]
    total: int
    limit: int
    offset: int


class AdminUserUpdateRequest(BaseModel):
    """Tous les champs optionnels : seuls ceux fournis sont modifiés."""
    role: UserRole | None = None
    status: AccountStatus | None = None


# --- Cours -----------------------------------------------------------

class AdminCourseIn(BaseModel):
    school_id: str
    title: str = Field(min_length=1, max_length=200)
    level: str | None = None
    duration_min: int | None = None
    color: str | None = None
    description: str | None = None
    status: ContentStatus = ContentStatus.DRAFT


class AdminCourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    title: str
    level: str | None = None
    duration_min: int | None = None
    color: str | None = None
    description: str | None = None
    status: ContentStatus
    created_at: datetime
    updated_at: datetime


class AdminCourseListResponse(BaseModel):
    items: list[AdminCourseOut]
    total: int
    limit: int
    offset: int


# --- Médias (upload d'images pour les sections de leçon) --------------------

class MediaUploadOut(BaseModel):
    url: str
    content_type: str
    size_bytes: int


# --- Leçons -----------------------------------------------------------

class AdminLessonObjectiveIn(BaseModel):
    label: str


class AdminLessonSectionIn(BaseModel):
    title: str
    body: str
    # Renseigné via l'URL renvoyée par POST /admin/media/images (upload
    # préalable, indépendant de l'ID de section — voir api/admin_media.py).
    image_url: str | None = None
    image_alt: str | None = None
    diagram: dict | None = None


class AdminLessonDepthLevelIn(BaseModel):
    depth_key: LessonDepthKey
    label: str
    title: str
    body: str


class AdminLessonIn(BaseModel):
    course_id: str
    skill_id: str | None = None
    demo_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    level: str | None = None
    duration_min: int | None = None
    summary: str | None = None
    example: str | None = None
    position: int = 0
    status: ContentStatus = ContentStatus.DRAFT
    objectives: list[str] = []
    sections: list[AdminLessonSectionIn] = []
    depth_levels: list[AdminLessonDepthLevelIn] = []


class AdminLessonOut(BaseModel):
    id: str
    course_id: str
    skill_id: str | None = None
    demo_id: str | None = None
    title: str
    level: str | None = None
    duration_min: int | None = None
    summary: str | None = None
    example: str | None = None
    position: int
    status: ContentStatus
    objectives: list[str] = []
    sections: list[AdminLessonSectionIn] = []
    depth_levels: list[AdminLessonDepthLevelIn] = []


class AdminLessonListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    title: str
    level: str | None = None
    position: int
    status: ContentStatus


class AdminLessonListResponse(BaseModel):
    items: list[AdminLessonListItemOut]
    total: int
    limit: int
    offset: int


# --- Import PDF -----------------------------------------------------------

class PdfImportResponse(BaseModel):
    document_id: uuid.UUID
    """Le document versé au corpus. Toujours présent, contrairement au cours."""
    # None pour un document de référence, importé sans création de cours.
    course_id: str | None = None
    lesson_id: str | None = None
    title: str
    pages_extracted: int
    warning: str | None = None
    # Rapport de qualité du nouveau moteur d'import (§28) : compteurs,
    # confiance moyenne et points à vérifier. Optionnel et purement additif —
    # les clients existants qui l'ignorent continuent de fonctionner, et il
    # vaut None si la reconstruction a échoué.
    report: dict | None = None


# --- Prévisualisation avant validation (§29 cahier import PDF) --------------
# L'import crée un cours en brouillon dès l'envoi du fichier : rien ne permet
# de voir ce que le moteur a compris avant que ce soit écrit. Ces schémas
# décrivent la même analyse, rendue sans rien enregistrer.

class PdfPreviewBlockOut(BaseModel):
    kind: str
    confidence: float
    preview: str
    """Premiers caractères du bloc — de quoi reconnaître son contenu dans
    l'arbre, sans transporter tout le document dans la réponse."""
    items: list | dict | None = None


class PdfPreviewSectionOut(BaseModel):
    title: str
    level: int
    confidence: float
    page_start: int | None = None
    page_end: int | None = None
    blocks: list[PdfPreviewBlockOut] = []
    children: list["PdfPreviewSectionOut"] = []


class PdfPreviewResponse(BaseModel):
    title: str
    pages: int
    report: dict
    sections: list[PdfPreviewSectionOut] = []


# --- Quiz (§15 cahier fonctionnel) -----------------------------------------
# ADMIN et SUPER_ADMIN peuvent tous deux gérer les quiz (cf. require_content_admin
# dans api/admin_quiz.py) — même périmètre que cours/leçons.
#
# Simplification assumée pour cette première version : chaque question est
# la propriété exclusive du quiz qui la contient (remplacement intégral à
# chaque sauvegarde, même principe que les sections de leçon). Voir le
# docstring de repositories/admin_quiz_repository.py pour le détail.

class AdminQuestionOptionIn(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False


class AdminQuestionIn(BaseModel):
    question_text: str = Field(min_length=1)
    explanation: str | None = None
    difficulty: int = Field(default=1, ge=1, le=5)
    options: list[AdminQuestionOptionIn] = []


class AdminQuizIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: QuizKind = QuizKind.PRACTICE
    lesson_id: str | None = None
    course_id: str | None = None
    skill_id: str | None = None
    pass_threshold: int = Field(default=70, ge=0, le=100)
    status: ContentStatus = ContentStatus.DRAFT
    questions: list[AdminQuestionIn] = []


class AdminQuestionOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    option_text: str
    is_correct: bool


class AdminQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    question_text: str
    explanation: str | None = None
    difficulty: int
    options: list[AdminQuestionOptionOut] = []


class AdminQuizOut(BaseModel):
    id: uuid.UUID
    title: str
    kind: QuizKind
    lesson_id: str | None = None
    course_id: str | None = None
    skill_id: str | None = None
    pass_threshold: int
    status: ContentStatus
    questions: list[AdminQuestionOut] = []


class AdminQuizListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    kind: QuizKind
    lesson_id: str | None = None
    course_id: str | None = None
    skill_id: str | None = None
    status: ContentStatus
    question_count: int = 0


class AdminQuizListResponse(BaseModel):
    items: list[AdminQuizListItemOut]
    total: int
    limit: int
    offset: int


# --- Progression globale (SUPER_ADMIN) ---------------------------------

class AdminLearnerProgressSummaryOut(BaseModel):
    """Une ligne de la liste des apprenants côté dashboard de progression."""
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    status: AccountStatus
    lessons_completed: int
    lessons_total_published: int
    quizzes_attempted: int
    quizzes_passed: int
    quiz_average_score: float | None = None
    labs_completed: int
    last_activity_at: datetime | None = None


class AdminLearnerProgressListResponse(BaseModel):
    items: list[AdminLearnerProgressSummaryOut]
    total: int
    limit: int
    offset: int


class AdminLearnerLessonProgressOut(BaseModel):
    lesson_id: str
    lesson_title: str
    course_id: str
    status: LessonProgressStatus
    progress_pct: int
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AdminLearnerQuizAttemptOut(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    score: int
    passed: bool
    started_at: datetime
    completed_at: datetime | None = None


class AdminLearnerLabResultOut(BaseModel):
    result_id: uuid.UUID
    lab_id: str
    lab_title: str
    mode: str | None = None
    completed: bool
    score: int | None = None
    submitted_at: datetime | None = None


class AdminLearnerProgressDetailOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    status: AccountStatus
    lessons: list[AdminLearnerLessonProgressOut]
    quiz_attempts: list[AdminLearnerQuizAttemptOut]
    lab_results: list[AdminLearnerLabResultOut]


# --- Certifications (SUPER_ADMIN) -------------------------------------------
# Le seed ne peut inférer depuis le texte libre du prototype (« Quiz ≥ 75 % »,
# « Examen technique »…) ni la compétence, ni le cours, ni le lab concerné —
# cette page permet à un SUPER_ADMIN d'attacher explicitement chaque critère
# à une référence structurée, ce qui le rend enfin vérifiable automatiquement
# par CertificationService (cf. services/certification_service.py).

class AdminCertificationRequirementIn(BaseModel):
    requirement_type: CertificationRequirementType
    description: str | None = None
    course_id: str | None = None
    lab_id: str | None = None
    skill_id: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)


class AdminCertificationRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_type: CertificationRequirementType
    description: str | None = None
    course_id: str | None = None
    lab_id: str | None = None
    skill_id: str | None = None
    min_score: int | None = None
    position: int


class AdminCertificationOut(BaseModel):
    id: str
    title: str
    level: str | None = None
    description: str | None = None
    status: ContentStatus
    requirements: list[AdminCertificationRequirementOut] = []


class AdminCertificationListItemOut(BaseModel):
    id: str
    title: str
    level: str | None = None
    status: ContentStatus
    requirement_count: int
    linked_requirement_count: int
    """Nombre de critères qui référencent déjà une compétence/un cours/un lab
    — indicateur rapide, dans la liste, de ce qui reste à traiter."""


class AdminCertificationListResponse(BaseModel):
    items: list[AdminCertificationListItemOut]
