from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    short_name: str
    color: str
    description: str | None = None


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    name: str
    description: str | None = None


class ProfileTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str


class LessonSummaryOut(BaseModel):
    """Aperçu d'une leçon dans le cadre d'un cours — le contenu complet
    (sections, objectifs, niveaux de profondeur) n'est exposé que via
    l'endpoint dédié /api/lessons/{id}, réservé aux utilisateurs authentifiés
    (§4.1 cahier fonctionnel : le visiteur n'a accès qu'aux informations
    publiques sur les formations, pas au contenu pédagogique complet)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    level: str | None = None
    duration_min: int | None = None
    position: int


class LabListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    school_id: str | None = None
    level: str | None = None
    duration_min: int | None = None
    color: str | None = None
    description: str | None = None


class LabInteractiveStepOut(BaseModel):
    key: str
    title: str
    summary: str
    detail: str
    highlights: list[str] = []


class LabDetailOut(LabListOut):
    environment: str | None = None
    instructions: str | None = None
    dataset_ref: str | None = None
    deliverable: str | None = None
    evaluation_note: str | None = None
    modes: list[str] = []
    skills: list[str] = []
    interactive_steps: list[LabInteractiveStepOut] | None = None


class CourseListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    title: str
    level: str | None = None
    duration_min: int | None = None
    color: str | None = None
    description: str | None = None


class ResourceOut(BaseModel):
    """Entrée de bibliographie — source réelle utilisée pour rédiger le
    contenu du cours (cf. resources/resource_courses, reliées ici pour la
    première fois à une route API)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    type: str | None = None
    url: str | None = None
    publisher: str | None = None
    year: int | None = None
    description: str | None = None


class CourseDetailOut(CourseListOut):
    lessons: list[LessonSummaryOut] = []
    final_quiz_id: str | None = None
    resources: list[ResourceOut] = []


class PathwayListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    profile_label: str | None = None
    level: str | None = None
    duration_label: str | None = None
    color: str | None = None
    description: str | None = None


class PathwayDetailOut(PathwayListOut):
    courses: list[CourseListOut] = []


class Page(BaseModel):
    """Enveloppe de pagination générique."""
    total: int
    limit: int
    offset: int


class CourseListResponse(Page):
    items: list[CourseListOut]


class PathwayListResponse(Page):
    items: list[PathwayListOut]


class LabListResponse(Page):
    items: list[LabListOut]
