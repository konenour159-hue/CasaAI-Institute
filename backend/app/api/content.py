"""
Endpoints de lecture du contenu pédagogique (§9 catalogue, §6 routes
publiques du cahier fonctionnel ; §5 API "Cours" du cahier technique).

Accès public (visiteur non authentifié) : seul le contenu au statut
PUBLISHED est exposé, jamais les brouillons ni les contenus archivés.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.content_repository import ContentRepository
from app.schemas.content import (
    CourseDetailOut,
    CourseListOut,
    CourseListResponse,
    LabDetailOut,
    LabListOut,
    LabListResponse,
    LessonSummaryOut,
    PathwayDetailOut,
    PathwayListOut,
    PathwayListResponse,
    ResourceOut,
    SchoolOut,
    SkillOut,
)

router = APIRouter(prefix="/api", tags=["content"])


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(db: Session = Depends(get_db)) -> list:
    return ContentRepository(db).list_schools()


@router.get("/skills", response_model=list[SkillOut])
def list_skills(
    school_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list:
    return ContentRepository(db).list_skills(school_id=school_id)


@router.get("/courses", response_model=CourseListResponse)
def list_courses(
    school_id: str | None = Query(default=None),
    level: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> CourseListResponse:
    items, total = ContentRepository(db).list_courses(
        school_id=school_id, level=level, limit=limit, offset=offset
    )
    return CourseListResponse(
        items=[CourseListOut.model_validate(c) for c in items], total=total, limit=limit, offset=offset
    )


@router.get("/courses/{course_id}", response_model=CourseDetailOut)
def get_course(course_id: str, db: Session = Depends(get_db)) -> CourseDetailOut:
    repo = ContentRepository(db)
    result = repo.get_course(course_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cours introuvable.")
    course, lessons = result
    return CourseDetailOut(
        **CourseListOut.model_validate(course).model_dump(),
        lessons=[LessonSummaryOut.model_validate(l) for l in lessons],
        final_quiz_id=repo.get_final_quiz_id(course_id),
        resources=[ResourceOut.model_validate(r) for r in repo.get_course_resources(course_id)],
    )


@router.get("/pathways", response_model=PathwayListResponse)
def list_pathways(
    level: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PathwayListResponse:
    items, total = ContentRepository(db).list_pathways(level=level, limit=limit, offset=offset)
    return PathwayListResponse(
        items=[PathwayListOut.model_validate(p) for p in items], total=total, limit=limit, offset=offset
    )


@router.get("/pathways/{pathway_id}", response_model=PathwayDetailOut)
def get_pathway(pathway_id: str, db: Session = Depends(get_db)) -> PathwayDetailOut:
    result = ContentRepository(db).get_pathway(pathway_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcours introuvable.")
    pathway, courses = result
    return PathwayDetailOut(
        **PathwayListOut.model_validate(pathway).model_dump(),
        courses=[CourseListOut.model_validate(c) for c in courses],
    )


@router.get("/labs", response_model=LabListResponse)
def list_labs(
    school_id: str | None = Query(default=None),
    level: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> LabListResponse:
    items, total = ContentRepository(db).list_labs(school_id=school_id, level=level, limit=limit, offset=offset)
    return LabListResponse(
        items=[LabListOut.model_validate(l) for l in items], total=total, limit=limit, offset=offset
    )


@router.get("/labs/{lab_id}", response_model=LabDetailOut)
def get_lab(lab_id: str, db: Session = Depends(get_db)) -> LabDetailOut:
    result = ContentRepository(db).get_lab(lab_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab introuvable.")
    lab, modes, skill_ids = result
    return LabDetailOut(
        **LabListOut.model_validate(lab).model_dump(), modes=modes, skills=skill_ids,
        interactive_steps=lab.interactive_steps,
    )
