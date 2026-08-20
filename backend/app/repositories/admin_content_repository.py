from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import School, Skill
from app.models.content import (
    Course,
    Demo,
    Lesson,
    LessonDepthLevel,
    LessonObjective,
    LessonSection,
)
from app.schemas.admin import AdminCourseIn, AdminLessonIn


def _slugify(text: str) -> str:
    """Identifiant lisible à partir d'un titre — miroir simplifié du style
    d'ID déjà utilisé dans le contenu seedé (ex: 'agent-engineering')."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or str(uuid.uuid4())[:8]


class AdminContentRepository:
    def __init__(self, db: Session):
        self.db = db

    def school_exists(self, school_id: str) -> bool:
        return self.db.get(School, school_id) is not None

    def skill_exists(self, skill_id: str) -> bool:
        return self.db.get(Skill, skill_id) is not None

    def demo_exists(self, demo_id: str) -> bool:
        return self.db.get(Demo, demo_id) is not None

    def get_course_any_status(self, course_id: str) -> Course | None:
        return self.db.get(Course, course_id)

    def list_courses_any_status(
        self, *, school_id: str | None = None, status_filter=None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Course], int]:
        from sqlalchemy import func

        stmt = select(Course)
        if school_id:
            stmt = stmt.where(Course.school_id == school_id)
        if status_filter:
            stmt = stmt.where(Course.status == status_filter)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            self.db.execute(stmt.order_by(Course.title).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def unique_course_id(self, base: str) -> str:
        candidate = base
        i = 2
        while self.db.get(Course, candidate) is not None:
            candidate = f"{base}-{i}"
            i += 1
        return candidate

    def create_course(self, data: AdminCourseIn, *, course_id: str | None = None) -> Course:
        cid = course_id or self.unique_course_id(_slugify(data.title))
        course = Course(
            id=cid, school_id=data.school_id, title=data.title, level=data.level,
            duration_min=data.duration_min, color=data.color, description=data.description,
            status=data.status,
        )
        self.db.add(course)
        self.db.flush()
        return course

    def update_course(self, course: Course, data: AdminCourseIn) -> Course:
        course.school_id = data.school_id
        course.title = data.title
        course.level = data.level
        course.duration_min = data.duration_min
        course.color = data.color
        course.description = data.description
        course.status = data.status
        self.db.flush()
        return course

    def delete_course(self, course: Course) -> None:
        self.db.delete(course)
        self.db.flush()

    def get_lesson_any_status(self, lesson_id: str) -> Lesson | None:
        return self.db.execute(
            select(Lesson)
            .options(
                selectinload(Lesson.objectives),
                selectinload(Lesson.sections),
                selectinload(Lesson.depth_levels),
            )
            .where(Lesson.id == lesson_id)
        ).scalar_one_or_none()

    def list_lessons_any_status(
        self, *, course_id: str | None = None, status_filter=None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Lesson], int]:
        from sqlalchemy import func

        stmt = select(Lesson)
        if course_id:
            stmt = stmt.where(Lesson.course_id == course_id)
        if status_filter:
            stmt = stmt.where(Lesson.status == status_filter)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            self.db.execute(stmt.order_by(Lesson.course_id, Lesson.position).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def unique_lesson_id(self, base: str) -> str:
        candidate = base
        i = 2
        while self.db.get(Lesson, candidate) is not None:
            candidate = f"{base}-{i}"
            i += 1
        return candidate

    def create_lesson(self, data: AdminLessonIn, *, lesson_id: str | None = None) -> Lesson:
        lid = lesson_id or self.unique_lesson_id(_slugify(data.title))
        lesson = Lesson(
            id=lid, course_id=data.course_id, skill_id=data.skill_id, demo_id=data.demo_id,
            title=data.title, level=data.level, duration_min=data.duration_min,
            summary=data.summary, example=data.example, position=data.position, status=data.status,
        )
        self.db.add(lesson)
        self.db.flush()
        self._replace_nested(lesson, data)
        self.db.flush()
        return lesson

    def update_lesson(self, lesson: Lesson, data: AdminLessonIn) -> Lesson:
        lesson.course_id = data.course_id
        lesson.skill_id = data.skill_id
        lesson.demo_id = data.demo_id
        lesson.title = data.title
        lesson.level = data.level
        lesson.duration_min = data.duration_min
        lesson.summary = data.summary
        lesson.example = data.example
        lesson.position = data.position
        lesson.status = data.status
        self.db.flush()
        self._replace_nested(lesson, data)
        self.db.flush()
        return lesson

    def _replace_nested(self, lesson: Lesson, data: AdminLessonIn) -> None:
        """Remplace intégralement objectifs/sections/niveaux de profondeur —
        même principe (simple et idempotent) que scripts/seed.py."""
        self.db.query(LessonObjective).filter(LessonObjective.lesson_id == lesson.id).delete()
        for pos, label in enumerate(data.objectives):
            self.db.add(LessonObjective(lesson_id=lesson.id, position=pos, label=label))

        self.db.query(LessonSection).filter(LessonSection.lesson_id == lesson.id).delete()
        for pos, sec in enumerate(data.sections):
            self.db.add(LessonSection(
                lesson_id=lesson.id, position=pos, title=sec.title, body=sec.body,
                image_url=sec.image_url, image_alt=sec.image_alt, diagram=sec.diagram,
            ))

        self.db.query(LessonDepthLevel).filter(LessonDepthLevel.lesson_id == lesson.id).delete()
        for dl in data.depth_levels:
            self.db.add(LessonDepthLevel(
                lesson_id=lesson.id, depth_key=dl.depth_key, label=dl.label, title=dl.title, body=dl.body,
            ))

    def delete_lesson(self, lesson: Lesson) -> None:
        self.db.delete(lesson)
        self.db.flush()
