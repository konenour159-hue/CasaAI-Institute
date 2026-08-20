from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Skill
from app.models.content import Lesson
from app.models.enums import ContentStatus, LessonProgressStatus, QuizKind
from app.models.lab import Lab
from app.models.progress import LabResult, UserLessonProgress, UserSkill, QuizAttempt, QuizAttemptAnswer
from app.models.quiz import Question, QuestionOption, Quiz, quiz_questions


class ProgressRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Leçons -----------------------------------------------------------

    def get_lesson_detail(self, lesson_id: str) -> Lesson | None:
        return self.db.execute(
            select(Lesson)
            .options(
                selectinload(Lesson.objectives),
                selectinload(Lesson.sections),
                selectinload(Lesson.depth_levels),
            )
            .where(Lesson.id == lesson_id, Lesson.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none()

    def get_validation_quiz_id(self, lesson_id: str) -> str | None:
        """Quiz VALIDATION publié rattaché à cette leçon, s'il existe (§15
        cahier fonctionnel). Sans cet appel, un quiz VALIDATION créé pour la
        leçon resterait inatteignable côté apprenant (aucune autre route ne
        permet de le retrouver par lesson_id)."""
        quiz_id = self.db.execute(
            select(Quiz.id).where(
                Quiz.lesson_id == lesson_id, Quiz.kind == QuizKind.VALIDATION, Quiz.status == ContentStatus.PUBLISHED
            )
        ).scalar_one_or_none()
        return str(quiz_id) if quiz_id else None

    def mark_lesson_complete(self, user_id: uuid.UUID, lesson_id: str) -> UserLessonProgress:
        progress = self.db.get(UserLessonProgress, (user_id, lesson_id))
        now = datetime.now(timezone.utc)
        if progress is None:
            progress = UserLessonProgress(
                user_id=user_id, lesson_id=lesson_id,
                status=LessonProgressStatus.COMPLETED, progress_pct=100,
                started_at=now, completed_at=now,
            )
            self.db.add(progress)
        else:
            progress.status = LessonProgressStatus.COMPLETED
            progress.progress_pct = 100
            progress.completed_at = now
            if progress.started_at is None:
                progress.started_at = now
        self.db.flush()
        return progress

    def list_user_progress(self, user_id: uuid.UUID) -> list[tuple[UserLessonProgress, Lesson]]:
        rows = self.db.execute(
            select(UserLessonProgress, Lesson)
            .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
            .where(UserLessonProgress.user_id == user_id)
            .order_by(UserLessonProgress.updated_at.desc())
        ).all()
        return [(p, l) for p, l in rows]

    # --- Compétences -----------------------------------------------------

    def list_user_skills(self, user_id: uuid.UUID) -> list[tuple[UserSkill, Skill]]:
        rows = self.db.execute(
            select(UserSkill, Skill)
            .join(Skill, Skill.id == UserSkill.skill_id)
            .where(UserSkill.user_id == user_id)
            .order_by(Skill.name)
        ).all()
        return [(us, s) for us, s in rows]

    def bump_skill_mastery(self, user_id: uuid.UUID, skill_id: str, *, max_level: int = 4) -> None:
        user_skill = self.db.get(UserSkill, (user_id, skill_id))
        if user_skill is None:
            user_skill = UserSkill(user_id=user_id, skill_id=skill_id, mastery_level=1)
            self.db.add(user_skill)
        elif user_skill.mastery_level < max_level:
            user_skill.mastery_level += 1
        self.db.flush()

    # --- Quiz -----------------------------------------------------------

    def list_all_quizzes(self) -> list[Quiz]:
        """Catalogue complet des quiz publiés (GET /api/quizzes) — permet de
        parcourir tous les quiz existants sans devoir déjà connaître la
        compétence, la leçon ou le cours auquel chacun est rattaché."""
        return list(
            self.db.execute(
                select(Quiz).where(Quiz.status == ContentStatus.PUBLISHED).order_by(Quiz.title)
            ).scalars()
        )

    def get_quiz_with_questions(self, quiz_id: uuid.UUID) -> tuple[Quiz, list[tuple[Question, list[QuestionOption]]]] | None:
        quiz = self.db.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none()
        if quiz is None:
            return None
        return quiz, self._load_questions(quiz.id)

    def get_practice_quiz_by_skill(self, skill_id: str) -> tuple[Quiz, list[tuple[Question, list[QuestionOption]]]] | None:
        """Le seed assemble un quiz d'entraînement par compétence (cf.
        scripts/seed.py) ; ce lookup permet au frontend de le retrouver sans
        connaître son UUID à l'avance (ex: bouton "S'entraîner" sur une
        compétence du dashboard)."""
        quiz = self.db.execute(
            select(Quiz).where(
                Quiz.skill_id == skill_id, Quiz.kind == QuizKind.PRACTICE, Quiz.status == ContentStatus.PUBLISHED
            )
        ).scalar_one_or_none()
        if quiz is None:
            return None
        return quiz, self._load_questions(quiz.id)

    def _load_questions(self, quiz_id: uuid.UUID) -> list[tuple[Question, list[QuestionOption]]]:
        question_ids = list(
            self.db.execute(
                select(quiz_questions.c.question_id)
                .where(quiz_questions.c.quiz_id == quiz_id)
                .order_by(quiz_questions.c.position)
            ).scalars()
        )
        questions_with_options: list[tuple[Question, list[QuestionOption]]] = []
        for qid in question_ids:
            question = self.db.get(Question, qid)
            options = list(
                self.db.execute(
                    select(QuestionOption)
                    .where(QuestionOption.question_id == qid)
                    .order_by(QuestionOption.position)
                ).scalars()
            )
            questions_with_options.append((question, options))
        return questions_with_options

    def get_correct_options(self, question_ids: list[str]) -> dict[str, tuple[uuid.UUID, str | None]]:
        """Pour chaque question, renvoie (id de la bonne option, explication)."""
        result: dict[str, tuple[uuid.UUID, str | None]] = {}
        for qid in question_ids:
            option = self.db.execute(
                select(QuestionOption).where(
                    QuestionOption.question_id == qid, QuestionOption.is_correct.is_(True)
                )
            ).scalar_one_or_none()
            question = self.db.get(Question, qid)
            if option is not None:
                result[qid] = (option.id, question.explanation if question else None)
        return result

    def create_quiz_attempt(
        self, *, user_id: uuid.UUID, quiz_id: uuid.UUID, score: int, passed: bool,
        answers: list[tuple[str, uuid.UUID | None, bool]],
    ) -> QuizAttempt:
        now = datetime.now(timezone.utc)
        attempt = QuizAttempt(
            user_id=user_id, quiz_id=quiz_id, score=score, passed=passed,
            started_at=now, completed_at=now,
        )
        self.db.add(attempt)
        self.db.flush()
        for question_id, selected_option_id, is_correct in answers:
            self.db.add(QuizAttemptAnswer(
                attempt_id=attempt.id, question_id=question_id,
                selected_option_id=selected_option_id, is_correct=is_correct,
            ))
        self.db.flush()
        return attempt

    def list_quiz_history(self, user_id: uuid.UUID) -> list[tuple[QuizAttempt, Quiz]]:
        rows = self.db.execute(
            select(QuizAttempt, Quiz)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.started_at.desc())
        ).all()
        return [(a, q) for a, q in rows]

    # --- Labs -----------------------------------------------------------

    def lab_exists_published(self, lab_id: str) -> bool:
        return self.db.execute(
            select(Lab.id).where(Lab.id == lab_id, Lab.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none() is not None

    def create_lab_result(
        self, *, user_id: uuid.UUID, lab_id: str, mode: str | None,
        submission: dict | None, score: int | None,
    ) -> LabResult:
        result = LabResult(
            user_id=user_id, lab_id=lab_id, mode=mode, completed=True,
            score=score, submission=submission, submitted_at=datetime.now(timezone.utc),
        )
        self.db.add(result)
        self.db.flush()
        return result

    def list_lab_results(self, user_id: uuid.UUID) -> list[LabResult]:
        return list(
            self.db.execute(
                select(LabResult)
                .where(LabResult.user_id == user_id)
                .order_by(LabResult.submitted_at.desc())
            ).scalars()
        )
