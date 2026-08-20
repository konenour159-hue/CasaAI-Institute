"""
Gestion des cours et leçons côté admin (§22, §23 cahier fonctionnel).
Valide l'existence des références (école, compétence, démo) avant
d'écrire, plutôt que de laisser une erreur de contrainte de clé étrangère
remonter telle quelle jusqu'au client.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.content import Course, Lesson
from app.repositories.admin_content_repository import AdminContentRepository
from app.schemas.admin import AdminCourseIn, AdminLessonIn


class ValidationError(Exception):
    pass


class CourseNotFoundError(Exception):
    pass


class LessonNotFoundError(Exception):
    pass


class AdminContentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminContentRepository(db)

    # --- Cours -----------------------------------------------------------

    def create_course(self, data: AdminCourseIn) -> Course:
        if not self.repo.school_exists(data.school_id):
            raise ValidationError(f"École '{data.school_id}' introuvable.")
        course = self.repo.create_course(data)
        self.db.commit()
        self.db.refresh(course)
        return course

    def update_course(self, course_id: str, data: AdminCourseIn) -> Course:
        course = self.repo.get_course_any_status(course_id)
        if course is None:
            raise CourseNotFoundError(f"Cours '{course_id}' introuvable.")
        if not self.repo.school_exists(data.school_id):
            raise ValidationError(f"École '{data.school_id}' introuvable.")
        course = self.repo.update_course(course, data)
        self.db.commit()
        self.db.refresh(course)
        return course

    def delete_course(self, course_id: str) -> None:
        course = self.repo.get_course_any_status(course_id)
        if course is None:
            raise CourseNotFoundError(f"Cours '{course_id}' introuvable.")
        self.repo.delete_course(course)
        self.db.commit()

    # --- Leçons -----------------------------------------------------------

    def _validate_lesson_refs(self, data: AdminLessonIn) -> None:
        if self.repo.get_course_any_status(data.course_id) is None:
            raise ValidationError(f"Cours '{data.course_id}' introuvable.")
        if data.skill_id and not self.repo.skill_exists(data.skill_id):
            raise ValidationError(f"Compétence '{data.skill_id}' introuvable.")
        if data.demo_id and not self.repo.demo_exists(data.demo_id):
            raise ValidationError(f"Démo '{data.demo_id}' introuvable.")

    def create_lesson(self, data: AdminLessonIn) -> Lesson:
        self._validate_lesson_refs(data)
        lesson = self.repo.create_lesson(data)
        self.db.commit()
        self.db.refresh(lesson)
        return lesson

    def update_lesson(self, lesson_id: str, data: AdminLessonIn) -> Lesson:
        lesson = self.repo.get_lesson_any_status(lesson_id)
        if lesson is None:
            raise LessonNotFoundError(f"Leçon '{lesson_id}' introuvable.")
        self._validate_lesson_refs(data)
        lesson = self.repo.update_lesson(lesson, data)
        self.db.commit()
        self.db.refresh(lesson)
        return lesson

    def delete_lesson(self, lesson_id: str) -> None:
        lesson = self.repo.get_lesson_any_status(lesson_id)
        if lesson is None:
            raise LessonNotFoundError(f"Leçon '{lesson_id}' introuvable.")
        self.repo.delete_lesson(lesson)
        self.db.commit()
