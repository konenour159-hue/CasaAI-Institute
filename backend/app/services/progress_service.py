"""
Logique métier de progression apprenant (§15 cahier fonctionnel — quiz ;
§16 — compétences ; §14 — labs).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.repositories.progress_repository import ProgressRepository
from app.schemas.progress import QuizAnswerResultOut, QuizAttemptRequest, QuizAttemptResultOut


class QuizNotFoundError(Exception):
    pass


class UnknownQuestionError(Exception):
    """L'apprenant a soumis une réponse à une question qui n'appartient pas
    à ce quiz — tentative invalide, rejetée avant tout calcul de score."""


class ProgressService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProgressRepository(db)

    def complete_lesson(self, user_id: uuid.UUID, lesson_id: str):
        progress = self.repo.mark_lesson_complete(user_id, lesson_id)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def submit_quiz_attempt(
        self, *, user_id: uuid.UUID, quiz_id: uuid.UUID, payload: QuizAttemptRequest
    ) -> QuizAttemptResultOut:
        result = self.repo.get_quiz_with_questions(quiz_id)
        if result is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} introuvable.")
        quiz, questions_with_options = result

        valid_question_ids = {q.id for q, _ in questions_with_options}
        submitted = {a.question_id: a.selected_option_id for a in payload.answers}
        unknown = set(submitted) - valid_question_ids
        if unknown:
            raise UnknownQuestionError(
                f"Question(s) hors de ce quiz : {', '.join(sorted(unknown))}"
            )

        correct_map = self.repo.get_correct_options(list(valid_question_ids))

        answers_for_db: list[tuple[str, uuid.UUID | None, bool]] = []
        answer_results: list[QuizAnswerResultOut] = []
        correct_count = 0

        for question, options in questions_with_options:
            selected = submitted.get(question.id)
            correct_option_id, explanation = correct_map.get(question.id, (None, None))
            is_correct = selected is not None and correct_option_id is not None and selected == correct_option_id
            if is_correct:
                correct_count += 1
            answers_for_db.append((question.id, selected, is_correct))
            answer_results.append(QuizAnswerResultOut(
                question_id=question.id, selected_option_id=selected, is_correct=is_correct,
                correct_option_id=correct_option_id, explanation=explanation,
            ))

        total = len(questions_with_options)
        score = round(100 * correct_count / total) if total else 0
        passed = score >= quiz.pass_threshold

        attempt = self.repo.create_quiz_attempt(
            user_id=user_id, quiz_id=quiz_id, score=score, passed=passed, answers=answers_for_db,
        )

        # §16 cahier fonctionnel : suivre la progression de compétence. Règle
        # V1 volontairement simple : une tentative réussie fait progresser
        # d'un niveau la compétence associée au quiz (si définie), plafonnée.
        if passed and quiz.skill_id:
            self.repo.bump_skill_mastery(user_id, quiz.skill_id)

        self.db.commit()

        return QuizAttemptResultOut(
            attempt_id=attempt.id, score=score, passed=passed,
            correct_count=correct_count, total_questions=total, answers=answer_results,
        )

    def submit_lab(self, *, user_id: uuid.UUID, lab_id: str, mode: str | None,
                    submission: dict | None, score: int | None):
        if not self.repo.lab_exists_published(lab_id):
            return None
        result = self.repo.create_lab_result(
            user_id=user_id, lab_id=lab_id, mode=mode, submission=submission, score=score,
        )
        self.db.commit()
        self.db.refresh(result)
        return result
