"""
Gestion des quiz côté admin (§15 cahier fonctionnel). Valide l'existence des
références (leçon/cours/compétence) et la cohérence kind ↔ référence avant
d'écrire — même philosophie que AdminContentService pour cours/leçons.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.enums import QuizKind
from app.models.quiz import Quiz
from app.repositories.admin_content_repository import AdminContentRepository
from app.repositories.admin_quiz_repository import AdminQuizRepository
from app.schemas.admin import AdminQuizIn


class ValidationError(Exception):
    pass


class QuizNotFoundError(Exception):
    pass


_KIND_LABELS = {QuizKind.VALIDATION: "lesson_id", QuizKind.FINAL: "course_id", QuizKind.PRACTICE: "skill_id"}


class AdminQuizService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminQuizRepository(db)
        self.content_repo = AdminContentRepository(db)

    def _validate(self, data: AdminQuizIn) -> None:
        if data.lesson_id and self.content_repo.get_lesson_any_status(data.lesson_id) is None:
            raise ValidationError(f"Leçon '{data.lesson_id}' introuvable.")
        if data.course_id and self.content_repo.get_course_any_status(data.course_id) is None:
            raise ValidationError(f"Cours '{data.course_id}' introuvable.")
        if data.skill_id and not self.content_repo.skill_exists(data.skill_id):
            raise ValidationError(f"Compétence '{data.skill_id}' introuvable.")

        # Cohérence kind ↔ référence (§15 : un quiz VALIDATION valide une
        # leçon précise, un FINAL un cours, un PRACTICE une compétence).
        # Signalé comme erreur de saisie plutôt que silencieusement accepté,
        # pour éviter un quiz VALIDATION sans lesson_id qu'aucun apprenant ne
        # pourrait jamais atteindre (cf. le bug déjà corrigé côté accès).
        expected_field = _KIND_LABELS[data.kind]
        if expected_field == "lesson_id" and not data.lesson_id:
            raise ValidationError("Un quiz de type VALIDATION doit être rattaché à une leçon.")
        if expected_field == "course_id" and not data.course_id:
            raise ValidationError("Un quiz de type FINAL doit être rattaché à un cours.")
        if expected_field == "skill_id" and not data.skill_id:
            raise ValidationError("Un quiz de type PRACTICE doit être rattaché à une compétence.")

        for q in data.questions:
            if not any(o.is_correct for o in q.options):
                raise ValidationError(f"La question « {q.question_text[:60]} » n'a aucune bonne réponse marquée.")
            if len(q.options) < 2:
                raise ValidationError(f"La question « {q.question_text[:60]} » doit avoir au moins 2 options.")

    def create_quiz(self, data: AdminQuizIn) -> Quiz:
        self._validate(data)
        quiz = self.repo.create_quiz(data)
        self.db.commit()
        self.db.refresh(quiz)
        return quiz

    def update_quiz(self, quiz_id: uuid.UUID, data: AdminQuizIn) -> Quiz:
        quiz = self.repo.get_quiz_any_status(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz '{quiz_id}' introuvable.")
        self._validate(data)
        quiz = self.repo.update_quiz(quiz, data)
        self.db.commit()
        self.db.refresh(quiz)
        return quiz

    def delete_quiz(self, quiz_id: uuid.UUID) -> None:
        quiz = self.repo.get_quiz_any_status(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz '{quiz_id}' introuvable.")
        self.repo.delete_quiz(quiz)
        self.db.commit()
