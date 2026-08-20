import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../components/AppLink";
import { progressService } from "../services/progressService";
import { ApiError } from "../services/apiClient";
import { QuizSkeleton } from "../components/Skeleton";
import { RevealSection } from "../components/RevealSection";
import type { Quiz, QuizAttemptResult } from "../types/api";

function ChevronIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d={direction === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"}
        stroke="currentColor"
        strokeWidth={2.2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function QuizTakePage() {
  const { skillId, quizId } = useParams<{ skillId?: string; quizId?: string }>();
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QuizAttemptResult | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<"next" | "prev">("next");
  const slideRef = useRef<HTMLFieldSetElement>(null);
  const hasNavigatedRef = useRef(false);

  useEffect(() => {
    // Deux points d'entrée possibles vers cette page : un quiz d'entraînement
    // retrouvé via la compétence (/app/skills/:skillId/practice), ou un quiz
    // de validation de leçon / final de cours ouvert directement par son id
    // (/app/quizzes/:quizId) — cf. LessonPage / CourseDetailPage.
    const request = quizId
      ? progressService.getQuiz(quizId)
      : skillId
        ? progressService.getQuizBySkill(skillId)
        : null;
    if (!request) return;
    request.then(setQuiz).catch((err) => {
      if (err instanceof ApiError && err.status === 404) setNotFound(true);
    });
  }, [skillId, quizId]);

  // Le focus suit la question active : indispensable pour qu'un lecteur
  // d'écran annonce le changement de diapositive (légende "Question X/N"),
  // mais seulement après une vraie navigation — jamais au premier rendu, où
  // ça volerait le focus sans raison.
  useEffect(() => {
    if (hasNavigatedRef.current) slideRef.current?.focus();
  }, [currentIndex]);

  useEffect(() => {
    if (!quiz || result) return;
    const lastIndex = quiz.questions.length - 1;
    function onKeyDown(e: KeyboardEvent) {
      // Les flèches gauche/droite pilotent déjà la sélection à l'intérieur
      // d'un groupe de boutons radio (les options) — ne pas intercepter ce
      // cas, sous peine de faire changer de question pendant que l'apprenant
      // choisit une réponse au clavier.
      if (e.target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
      let target: number | null = null;
      if (e.key === "ArrowRight") target = currentIndex + 1;
      else if (e.key === "ArrowLeft") target = currentIndex - 1;
      if (target === null) return;
      const clamped = Math.max(0, Math.min(lastIndex, target));
      if (clamped === currentIndex) return;
      setDirection(clamped > currentIndex ? "next" : "prev");
      hasNavigatedRef.current = true;
      setCurrentIndex(clamped);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [quiz, result, currentIndex]);

  useEffect(() => {
    setCurrentIndex(0);
    hasNavigatedRef.current = false;
  }, [quiz?.id]);

  if (notFound) {
    return (
      <div style={{ maxWidth: 520 }}>
        <h2 style={{ marginBottom: 12 }}>Pas encore de quiz</h2>
        <p style={{ marginBottom: 24 }}>
          {skillId
            ? "Cette compétence n'a pas encore de quiz d'entraînement disponible."
            : "Ce quiz n'est pas disponible."}
        </p>
        <Link to="/app/dashboard" className="btn btn-secondary">
          Retour au dashboard
        </Link>
      </div>
    );
  }

  if (!quiz) return <QuizSkeleton />;

  const answeredCount = quiz.questions.filter((q) => answers[q.id]).length;
  const allAnswered = answeredCount === quiz.questions.length;
  const isFirst = currentIndex === 0;
  const isLast = currentIndex === quiz.questions.length - 1;
  const currentQuestion = quiz.questions[currentIndex];

  const goTo = (index: number) => {
    const clamped = Math.max(0, Math.min(quiz.questions.length - 1, index));
    if (clamped === currentIndex) return;
    setDirection(clamped > currentIndex ? "next" : "prev");
    hasNavigatedRef.current = true;
    setCurrentIndex(clamped);
  };

  const handleSubmit = async () => {
    if (!allAnswered) return;
    setSubmitting(true);
    try {
      const payload = quiz.questions.map((q) => ({
        question_id: q.id,
        selected_option_id: answers[q.id] ?? null,
      }));
      const res = await progressService.attemptQuiz(quiz.id, payload);
      setResult(res);
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    return (
      <div>
        <RevealSection as="div">
          <div
            className="card"
            style={{
              padding: 28,
              marginBottom: 32,
              borderColor: result.passed ? "var(--color-accent-teal)" : "var(--color-accent-coral)",
            }}
          >
            <span
              className="badge"
              style={{
                marginBottom: 12,
                background: result.passed ? "var(--color-accent-teal-soft)" : "var(--color-accent-coral-soft)",
                color: result.passed ? "var(--color-accent-teal)" : "var(--color-accent-coral)",
              }}
            >
              {result.passed ? "✓ Réussi" : "Non atteint"}
            </span>
            <h1 style={{ marginBottom: 6 }}>
              {result.score}<span style={{ fontSize: "1rem", color: "var(--color-text-muted)" }}>/100</span>
            </h1>
            <p>
              {result.correct_count} bonne{result.correct_count > 1 ? "s" : ""} réponse
              {result.correct_count > 1 ? "s" : ""} sur {result.total_questions}
            </p>
          </div>
        </RevealSection>

        <h2 style={{ marginBottom: 16 }}>Corrigé</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {quiz.questions.map((q, i) => {
            const answer = result.answers.find((a) => a.question_id === q.id);
            const correctOption = q.options.find((o) => o.id === answer?.correct_option_id);
            return (
              <RevealSection key={q.id} as="div" delayMs={Math.min(i, 8) * 50}>
                <div className="card" style={{ padding: 20 }}>
                  <p className="quiz-question" style={{ fontSize: "1.05rem", marginBottom: 0 }}>
                    {q.question_text}
                  </p>
                  <div className={`quiz-feedback ${answer?.is_correct ? "quiz-feedback-correct" : "quiz-feedback-incorrect"}`}>
                    <p style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-text)", fontWeight: 600 }}>
                      <span className="quiz-option-icon" aria-hidden>
                        {answer?.is_correct ? "✓" : "✕"}
                      </span>
                      {answer?.is_correct ? "Bonne réponse" : `Pas tout à fait — la bonne réponse était : ${correctOption?.option_text}`}
                    </p>
                    {answer?.explanation && (
                      <p style={{ marginTop: 6, color: "var(--color-text)" }}>{answer.explanation}</p>
                    )}
                  </div>
                </div>
              </RevealSection>
            );
          })}
        </div>

        <Link to="/app/dashboard" className="btn btn-primary" style={{ marginTop: 32 }}>
          Retour au dashboard
        </Link>
      </div>
    );
  }

  return (
    <div>
      <RevealSection as="div">
        <h1 style={{ marginBottom: 20 }}>{quiz.title}</h1>

        <div className="quiz-progress-label">
          <span>
            Question {currentIndex + 1}/{quiz.questions.length}
          </span>
          <span>
            {answeredCount}/{quiz.questions.length} répondues
          </span>
        </div>
        <div className="reading-progress-track" style={{ position: "static", marginBottom: 32 }}>
          <div
            className="reading-progress-fill"
            style={{ transform: `scaleX(${(currentIndex + 1) / quiz.questions.length})` }}
          />
        </div>
      </RevealSection>

      {/* Une question à la fois plutôt qu'un long défilement (demande
          explicite) : la carte se remonte à chaque changement de `key`, ce
          qui redéclenche l'animation d'entrée directionnelle définie dans
          index.css (glissement depuis la droite en avançant, depuis la
          gauche en reculant). */}
      <div className="quiz-slide-viewport" style={{ marginBottom: 24 }}>
        <fieldset
          key={currentQuestion.id}
          ref={slideRef}
          tabIndex={-1}
          className={`card quiz-slide ${direction === "next" ? "quiz-slide-in-next" : "quiz-slide-in-prev"}`}
          style={{ padding: 22, border: "1px solid var(--color-border)" }}
        >
          <legend
            className="mono"
            style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", padding: "0 6px" }}
          >
            Question {currentIndex + 1}/{quiz.questions.length}
          </legend>
          <p className="quiz-question">{currentQuestion.question_text}</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {currentQuestion.options.map((o) => {
              const selected = answers[currentQuestion.id] === o.id;
              return (
                <label key={o.id} className={`quiz-option${selected ? " selected" : ""}`}>
                  <input
                    type="radio"
                    name={currentQuestion.id}
                    value={o.id}
                    checked={selected}
                    onChange={() => setAnswers((prev) => ({ ...prev, [currentQuestion.id]: o.id }))}
                  />
                  {o.option_text}
                </label>
              );
            })}
          </div>
        </fieldset>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        <button
          type="button"
          className="quiz-nav-btn"
          data-dir="prev"
          onClick={() => goTo(currentIndex - 1)}
          disabled={isFirst}
          aria-label="Question précédente"
        >
          <ChevronIcon direction="left" />
        </button>

        <div className="quiz-dots" role="group" aria-label="Aller à une question">
          {quiz.questions.map((q, i) => (
            <button
              key={q.id}
              type="button"
              className={`quiz-dot${i === currentIndex ? " current" : ""}${answers[q.id] ? " answered" : ""}`}
              aria-label={`Question ${i + 1}${answers[q.id] ? ", répondue" : ""}`}
              aria-current={i === currentIndex ? "step" : undefined}
              onClick={() => goTo(i)}
            />
          ))}
        </div>

        {isLast ? (
          <button
            key="submit"
            type="button"
            className="btn btn-primary quiz-fade-in"
            onClick={handleSubmit}
            disabled={!allAnswered || submitting}
          >
            {submitting ? "Envoi…" : "Valider mes réponses"}
          </button>
        ) : (
          <button
            key="next"
            type="button"
            className="quiz-nav-btn quiz-fade-in"
            data-dir="next"
            onClick={() => goTo(currentIndex + 1)}
            aria-label="Question suivante"
          >
            <ChevronIcon direction="right" />
          </button>
        )}
      </div>

      {isLast && !allAnswered && (
        <p className="text-caption" style={{ marginTop: 12, textAlign: "center" }}>
          Il reste {quiz.questions.length - answeredCount} question
          {quiz.questions.length - answeredCount > 1 ? "s" : ""} sans réponse.
        </p>
      )}
    </div>
  );
}
