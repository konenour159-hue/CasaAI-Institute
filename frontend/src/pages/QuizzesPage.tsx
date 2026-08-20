import { useEffect, useState } from "react";
import { Link } from "../components/AppLink";
import { RevealSection } from "../components/RevealSection";
import { CardGridSkeleton } from "../components/Skeleton";
import { progressService } from "../services/progressService";
import type { QuizListItem } from "../types/api";

const KIND_LABEL: Record<QuizListItem["kind"], string> = {
  PRACTICE: "Entraînement",
  VALIDATION: "Validation de leçon",
  FINAL: "Quiz final de cours",
};

function quizLink(quiz: QuizListItem): string {
  // Un quiz PRACTICE se retrouve par compétence (le frontend n'a pas besoin
  // de connaître son UUID à l'avance) ; VALIDATION/FINAL par son UUID direct
  // — même logique que sur les pages leçon/cours (cf. LessonPage, CourseDetailPage).
  if (quiz.kind === "PRACTICE" && quiz.skill_id) {
    return `/app/skills/${quiz.skill_id}/practice`;
  }
  return `/app/quizzes/${quiz.id}`;
}

export function QuizzesPage() {
  const [quizzes, setQuizzes] = useState<QuizListItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    progressService
      .listQuizzes()
      .then(setQuizzes)
      .catch(() => setError(true));
  }, []);

  if (error) return <p className="error-text">Impossible de charger les quiz pour le moment.</p>;

  return (
    <div>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.8rem", marginBottom: 8 }}>Quiz</h1>
        <p style={{ marginBottom: 40 }}>Tous les quiz disponibles, tous cours et compétences confondus.</p>
      </RevealSection>

      {quizzes === null ? (
        <CardGridSkeleton />
      ) : quizzes.length === 0 ? (
        <p>Aucun quiz disponible pour le moment.</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
          {quizzes.map((q, i) => (
            <RevealSection key={q.id} as="div" delayMs={Math.min(i, 8) * 50} style={{ height: "100%" }}>
              <Link to={quizLink(q)} className="card" style={{ padding: 20, display: "block", height: "100%" }}>
                <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                  <span className="badge badge-teal">{KIND_LABEL[q.kind]}</span>
                  <span className="badge badge-gold">Seuil {q.pass_threshold}%</span>
                </div>
                <h3 style={{ fontSize: "1rem" }}>{q.title}</h3>
              </Link>
            </RevealSection>
          ))}
        </div>
      )}
    </div>
  );
}
