"""
Endpoints admin — cours, leçons, import PDF (§22, §23 cahier fonctionnel ;
§5 API "Cours" du cahier technique). Réservés au rôle ADMIN.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_content_admin
from app.db.session import get_db
from app.models.enums import ContentStatus
from app.models.user import User
from app.repositories.admin_content_repository import AdminContentRepository
from app.schemas.admin import (
    AdminCourseIn,
    AdminCourseListResponse,
    AdminCourseOut,
    AdminLessonIn,
    AdminLessonListResponse,
    AdminLessonOut,
    PdfImportResponse,
)
from app.services.admin_content_service import (
    AdminContentService,
    CourseNotFoundError,
    LessonNotFoundError,
    ValidationError,
)
from app.services.pdf_import_service import PdfExtractionError, PdfImportService

router = APIRouter(prefix="/api/admin", tags=["admin-content"])


def _lesson_to_out(lesson) -> AdminLessonOut:
    return AdminLessonOut(
        id=lesson.id, course_id=lesson.course_id, skill_id=lesson.skill_id, demo_id=lesson.demo_id,
        title=lesson.title, level=lesson.level, duration_min=lesson.duration_min,
        summary=lesson.summary, example=lesson.example, position=lesson.position, status=lesson.status,
        objectives=[o.label for o in lesson.objectives],
        sections=[
            {"title": s.title, "body": s.body, "image_url": s.image_url, "image_alt": s.image_alt, "diagram": s.diagram}
            for s in lesson.sections
        ],
        depth_levels=[
            {"depth_key": d.depth_key, "label": d.label, "title": d.title, "body": d.body}
            for d in lesson.depth_levels
        ],
    )


# --- Cours -----------------------------------------------------------

@router.get("/courses", response_model=AdminCourseListResponse)
def admin_list_courses(
    school_id: str | None = Query(default=None),
    status_filter: ContentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_content_admin),
) -> AdminCourseListResponse:
    items, total = AdminContentRepository(db).list_courses_any_status(
        school_id=school_id, status_filter=status_filter, limit=limit, offset=offset
    )
    return AdminCourseListResponse(
        items=[AdminCourseOut.model_validate(c) for c in items], total=total, limit=limit, offset=offset
    )


@router.get("/courses/{course_id}", response_model=AdminCourseOut)
def admin_get_course(
    course_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminCourseOut:
    course = AdminContentRepository(db).get_course_any_status(course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cours introuvable.")
    return AdminCourseOut.model_validate(course)


@router.post("/courses", response_model=AdminCourseOut, status_code=status.HTTP_201_CREATED)
def admin_create_course(
    payload: AdminCourseIn, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminCourseOut:
    try:
        course = AdminContentService(db).create_course(payload)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return AdminCourseOut.model_validate(course)


@router.put("/courses/{course_id}", response_model=AdminCourseOut)
def admin_update_course(
    course_id: str, payload: AdminCourseIn, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminCourseOut:
    try:
        course = AdminContentService(db).update_course(course_id, payload)
    except CourseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return AdminCourseOut.model_validate(course)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_course(
    course_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> None:
    try:
        AdminContentService(db).delete_course(course_id)
    except CourseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Leçons -----------------------------------------------------------

@router.get("/lessons", response_model=AdminLessonListResponse)
def admin_list_lessons(
    course_id: str | None = Query(default=None),
    status_filter: ContentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_content_admin),
) -> AdminLessonListResponse:
    items, total = AdminContentRepository(db).list_lessons_any_status(
        course_id=course_id, status_filter=status_filter, limit=limit, offset=offset
    )
    return AdminLessonListResponse(
        items=[{
            "id": l.id, "course_id": l.course_id, "title": l.title,
            "level": l.level, "position": l.position, "status": l.status,
        } for l in items],
        total=total, limit=limit, offset=offset,
    )


@router.get("/lessons/{lesson_id}", response_model=AdminLessonOut)
def admin_get_lesson(
    lesson_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminLessonOut:
    lesson = AdminContentRepository(db).get_lesson_any_status(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leçon introuvable.")
    return _lesson_to_out(lesson)


@router.post("/lessons", response_model=AdminLessonOut, status_code=status.HTTP_201_CREATED)
def admin_create_lesson(
    payload: AdminLessonIn, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminLessonOut:
    try:
        lesson = AdminContentService(db).create_lesson(payload)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return _lesson_to_out(lesson)


@router.put("/lessons/{lesson_id}", response_model=AdminLessonOut)
def admin_update_lesson(
    lesson_id: str, payload: AdminLessonIn, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> AdminLessonOut:
    try:
        lesson = AdminContentService(db).update_lesson(lesson_id, payload)
    except LessonNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return _lesson_to_out(lesson)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_lesson(
    lesson_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)
) -> None:
    try:
        AdminContentService(db).delete_lesson(lesson_id)
    except LessonNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Import PDF -----------------------------------------------------------

@router.post("/courses/import-pdf", response_model=PdfImportResponse, status_code=status.HTTP_201_CREATED)
async def admin_import_pdf(
    school_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_content_admin),
) -> PdfImportResponse:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Type de fichier non supporté : {file.content_type}. PDF attendu.",
        )

    file_bytes = await file.read()
    try:
        course, lesson, page_count, warning = PdfImportService(db).import_pdf(
            file_bytes=file_bytes, filename=file.filename or "import.pdf", school_id=school_id,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    except PdfExtractionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))

    return PdfImportResponse(
        course_id=course.id, lesson_id=lesson.id, title=course.title,
        pages_extracted=page_count, warning=warning,
    )
