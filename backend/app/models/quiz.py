from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, SmallInteger, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.content import CONTENT_STATUS_ENUM
from app.models.enums import ContentStatus, QuizKind


class QuestionBank(Base):
    __tablename__ = "question_banks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bank_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("question_banks.id", ondelete="SET NULL"))
    skill_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("skills.id", ondelete="SET NULL"))
    domain: Mapped[Optional[str]] = mapped_column(String)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", order_by="QuestionOption.position", cascade="all, delete-orphan"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[uuid.UUID] = uuid_pk()
    question_id: Mapped[str] = mapped_column(String, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    option_text: Mapped[str] = mapped_column(String, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")


class Quiz(Base, TimestampMixin):
    """Quiz réel (entraînement / validation / final), assemblé à partir du
    référentiel de questions. Cf. §15 cahier fonctionnel."""
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[QuizKind] = mapped_column(Enum(QuizKind, name="quiz_kind"), nullable=False, default=QuizKind.PRACTICE)
    lesson_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("lessons.id", ondelete="CASCADE"))
    course_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"))
    skill_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("skills.id", ondelete="SET NULL"))
    pass_threshold: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=70)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


quiz_questions = Table(
    "quiz_questions",
    Base.metadata,
    Column("quiz_id", UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), primary_key=True),
    Column("question_id", String, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
)
