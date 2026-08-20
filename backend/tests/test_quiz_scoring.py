"""Tests unitaires sur la notation des quiz (ProgressService.submit_quiz_attempt)
— le calcul du score, le seuil de réussite, et la progression de compétence
qui en découle sont la logique la plus sensible du parcours apprenant."""
from __future__ import annotations

import uuid

import pytest

from app.core.security import hash_password
from app.models.catalog import School, Skill
from app.models.enums import ContentStatus, QuizKind
from app.models.progress import UserSkill
from app.models.quiz import Question, QuestionOption, Quiz, quiz_questions
from app.models.user import User
from app.schemas.progress import QuizAnswerSubmission, QuizAttemptRequest
from app.services.progress_service import ProgressService, UnknownQuestionError


@pytest.fixture()
def learner(db_session):
    user = User(
        first_name="Ada", last_name="Lovelace", email="scorer@example.com",
        password_hash=hash_password("irrelevant-for-this-test"),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def quiz_with_two_questions(db_session):
    """Un quiz à 2 questions, seuil de réussite 70%, rattaché à une
    compétence — pour vérifier à la fois le score et la progression de
    compétence qu'un quiz réussi déclenche."""
    school = School(id="test-school", name="École de test", short_name="TEST", color="#000000")
    skill = Skill(id="test-skill", school_id=school.id, name="Compétence de test")
    db_session.add_all([school, skill])
    db_session.flush()

    quiz = Quiz(
        id=uuid.uuid4(), title="Quiz de test", kind=QuizKind.PRACTICE,
        skill_id=skill.id, pass_threshold=70, status=ContentStatus.PUBLISHED,
    )
    db_session.add(quiz)
    db_session.flush()

    questions = []
    for i in range(2):
        question = Question(id=f"test-q{i}", question_text=f"Question {i}", status=ContentStatus.PUBLISHED)
        db_session.add(question)
        db_session.flush()
        correct = QuestionOption(question_id=question.id, position=0, option_text="Bonne réponse", is_correct=True)
        wrong = QuestionOption(question_id=question.id, position=1, option_text="Mauvaise réponse", is_correct=False)
        db_session.add_all([correct, wrong])
        db_session.flush()
        db_session.execute(quiz_questions.insert().values(quiz_id=quiz.id, question_id=question.id, position=i))
        questions.append((question, correct, wrong))

    db_session.commit()
    return quiz, questions


def test_all_correct_answers_score_100_and_pass(db_session, quiz_with_two_questions, learner):
    quiz, questions = quiz_with_two_questions
    answers = [
        QuizAnswerSubmission(question_id=q.id, selected_option_id=correct.id)
        for q, correct, _wrong in questions
    ]

    result = ProgressService(db_session).submit_quiz_attempt(
        user_id=learner.id, quiz_id=quiz.id, payload=QuizAttemptRequest(answers=answers),
    )

    assert result.score == 100
    assert result.passed is True
    assert result.correct_count == 2
    assert result.total_questions == 2


def test_half_correct_scores_50_and_fails_a_70_threshold(db_session, quiz_with_two_questions, learner):
    quiz, questions = quiz_with_two_questions
    (q0, correct0, _), (q1, _, wrong1) = questions
    answers = [
        QuizAnswerSubmission(question_id=q0.id, selected_option_id=correct0.id),
        QuizAnswerSubmission(question_id=q1.id, selected_option_id=wrong1.id),
    ]

    result = ProgressService(db_session).submit_quiz_attempt(
        user_id=learner.id, quiz_id=quiz.id, payload=QuizAttemptRequest(answers=answers),
    )

    assert result.score == 50
    assert result.passed is False


def test_unanswered_question_counts_as_incorrect_not_as_an_error(db_session, quiz_with_two_questions, learner):
    quiz, questions = quiz_with_two_questions
    (q0, correct0, _), (q1, _, _) = questions
    # Une seule des deux questions répondue — l'autre reste absente du payload,
    # comme un apprenant qui n'a pas sélectionné d'option avant de valider.
    answers = [QuizAnswerSubmission(question_id=q0.id, selected_option_id=correct0.id)]

    result = ProgressService(db_session).submit_quiz_attempt(
        user_id=learner.id, quiz_id=quiz.id, payload=QuizAttemptRequest(answers=answers),
    )

    assert result.correct_count == 1
    assert result.total_questions == 2
    assert result.score == 50


def test_answer_to_a_question_outside_the_quiz_is_rejected(db_session, quiz_with_two_questions, learner):
    quiz, _questions = quiz_with_two_questions
    answers = [QuizAnswerSubmission(question_id="not-part-of-this-quiz", selected_option_id=None)]

    with pytest.raises(UnknownQuestionError):
        ProgressService(db_session).submit_quiz_attempt(
            user_id=learner.id, quiz_id=quiz.id, payload=QuizAttemptRequest(answers=answers),
        )


def test_passing_a_quiz_bumps_the_linked_skill_mastery(db_session, quiz_with_two_questions, learner):
    quiz, questions = quiz_with_two_questions
    answers = [
        QuizAnswerSubmission(question_id=q.id, selected_option_id=correct.id)
        for q, correct, _wrong in questions
    ]

    ProgressService(db_session).submit_quiz_attempt(
        user_id=learner.id, quiz_id=quiz.id, payload=QuizAttemptRequest(answers=answers),
    )

    user_skill = db_session.get(UserSkill, (learner.id, quiz.skill_id))
    assert user_skill is not None
    assert user_skill.mastery_level == 1


def test_failing_a_quiz_does_not_bump_skill_mastery(db_session, quiz_with_two_questions, learner):
    quiz, questions = quiz_with_two_questions
    (q0, _, wrong0), (q1, _, wrong1) = questions
    answers = [
        QuizAnswerSubmission(question_id=q0.id, selected_option_id=wrong0.id),
        QuizAnswerSubmission(question_id=q1.id, selected_option_id=wrong1.id),
    ]

    ProgressService(db_session).submit_quiz_attempt(
        user_id=learner.id, quiz_id=quiz.id, payload=QuizAttemptRequest(answers=answers),
    )

    user_skill = db_session.get(UserSkill, (learner.id, quiz.skill_id))
    assert user_skill is None
