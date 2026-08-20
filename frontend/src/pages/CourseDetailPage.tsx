import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../components/AppLink";
import { RevealSection } from "../components/RevealSection";
import { SchoolIcon } from "../components/ModuleIcon";
import { CourseSkeleton } from "../components/Skeleton";
import { useAuth } from "../stores/authStore";
import { contentService } from "../services/contentService";
import { certificationService } from "../services/certificationService";
import type { CourseCertificateEligibility, CourseDetail } from "../types/api";

export function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isAuthenticated } = useAuth();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [eligibility, setEligibility] = useState<CourseCertificateEligibility | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    contentService
      .getCourse(courseId)
      .then(setCourse)
      .catch(() => setNotFound(true));
  }, [courseId]);

  useEffect(() => {
    if (!courseId || !isAuthenticated) return;
    certificationService
      .getCourseCertificateEligibility(courseId)
      .then(setEligibility)
      .catch(() => setEligibility(null));
  }, [courseId, isAuthenticated]);

  const handleIssueCertificate = async () => {
    if (!courseId) return;
    setIssuing(true);
    setIssueError(null);
    try {
      await certificationService.issueCourseCertificate(courseId);
      const refreshed = await certificationService.getCourseCertificateEligibility(courseId);
      setEligibility(refreshed);
    } catch {
      setIssueError("Le certificat n'a pas pu être délivré — vérifiez que le seuil de 80% est atteint.");
    } finally {
      setIssuing(false);
    }
  };

  if (notFound) return <p className="error-text">Ce cours est introuvable.</p>;
  if (!course) return <CourseSkeleton />;

  const accent = course.color ?? "var(--color-accent-gold)";

  return (
    <div className="course-content">
      <RevealSection as="div">
        <SchoolIcon schoolId={course.school_id} color={accent} />

        <h1 style={{ marginBottom: 16 }}>{course.title}</h1>
        {course.description && (
          <p style={{ marginBottom: 40, fontSize: "1.0625rem", lineHeight: 1.7, color: "var(--color-text)" }}>
            {course.description}
          </p>
        )}
      </RevealSection>

      <h2 style={{ marginBottom: 16 }}>
        Leçons <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>({course.lessons.length})</span>
      </h2>

      <ol style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {course.lessons.map((lesson, i) => (
          <RevealSection
            key={lesson.id}
            as="li"
            delayMs={Math.min(i, 6) * 50}
            className="card"
            style={{ padding: "18px 22px", display: "flex", alignItems: "center", gap: 18, borderLeft: `3px solid ${accent}` }}
          >
            <span className="mono" style={{ color: accent, fontSize: "0.95rem", fontWeight: 600 }}>
              {String(i + 1).padStart(2, "0")}
            </span>
            <div style={{ flex: 1 }}>
              <p style={{ color: "var(--color-text)", fontWeight: 500, fontSize: "1rem" }}>{lesson.title}</p>
              {lesson.duration_min && (
                <p style={{ fontSize: "0.8rem" }}>{lesson.duration_min} min</p>
              )}
            </div>
            {isAuthenticated ? (
              <Link to={`/app/lessons/${lesson.id}`} className="btn btn-secondary">
                Ouvrir
              </Link>
            ) : (
              <Link to="/login" className="btn btn-secondary">
                Se connecter
              </Link>
            )}
          </RevealSection>
        ))}
      </ol>

      {course.final_quiz_id && (
        <RevealSection as="div" className="card" style={{ padding: 24, marginTop: 32, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
          <div>
            <h3 style={{ marginBottom: 6 }}>Quiz final</h3>
            <p style={{ fontSize: "0.88rem" }}>Validez l'ensemble des acquis de ce cours.</p>
          </div>
          <Link
            to={isAuthenticated ? `/app/quizzes/${course.final_quiz_id}` : "/login"}
            className="btn btn-primary"
            style={{ flexShrink: 0 }}
          >
            {isAuthenticated ? "Passer le quiz final" : "Se connecter"}
          </Link>
        </RevealSection>
      )}

      {eligibility && eligibility.quizzes.length > 0 && (
        <RevealSection as="div" className="card" style={{ padding: 24, marginTop: 32 }}>
          <h3 style={{ marginBottom: 6 }}>Certificat de module</h3>
          <p style={{ fontSize: "0.88rem", marginBottom: 18 }}>
            Réussissez tous les quiz de ce cours avec une moyenne d'au moins {eligibility.threshold}% pour obtenir
            votre certificat.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
            {eligibility.quizzes.map((q) => (
              <div
                key={q.quiz_id}
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem" }}
              >
                <span>{q.quiz_title}</span>
                <span
                  className="mono"
                  style={{ color: q.attempted ? "var(--color-accent-teal)" : "var(--color-text-muted)" }}
                >
                  {q.attempted ? `${q.best_score}%` : "non tenté"}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="mono" style={{ fontSize: "0.9rem" }}>
              Moyenne{eligibility.all_attempted ? "" : " partielle"} :{" "}
              {eligibility.average_score !== null ? `${eligibility.average_score}%` : "—"}
              {!eligibility.all_attempted && " (quiz restants)"}
            </span>

            {eligibility.already_issued ? (
              <span className="badge badge-teal">
                Certificat obtenu {eligibility.issued_at && `le ${new Date(eligibility.issued_at).toLocaleDateString("fr-FR")}`}
              </span>
            ) : (
              <button
                className="btn btn-primary"
                disabled={!eligibility.eligible || issuing}
                onClick={handleIssueCertificate}
              >
                {issuing ? "…" : "Obtenir mon certificat"}
              </button>
            )}
          </div>
          {issueError && <p className="error-text" style={{ marginTop: 12, fontSize: "0.85rem" }}>{issueError}</p>}
        </RevealSection>
      )}

      {course.resources.length > 0 && (
        <RevealSection as="div" style={{ marginTop: 32 }}>
          <h2 style={{ marginBottom: 16 }}>Bibliographie</h2>
          <p style={{ fontSize: "0.85rem", marginBottom: 16 }}>
            Sources utilisées pour rédiger le contenu de ce cours.
          </p>
          <ol style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            {course.resources.map((r) => (
              <li key={r.id} className="card" style={{ padding: "14px 18px" }}>
                {r.url ? (
                  <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-accent-blue)", fontWeight: 500 }}>
                    {r.title}
                  </a>
                ) : (
                  <span style={{ color: "var(--color-text)", fontWeight: 500 }}>{r.title}</span>
                )}
                <p style={{ fontSize: "0.8rem", marginTop: 4 }}>
                  {[r.publisher, r.year, r.type].filter(Boolean).join(" · ")}
                </p>
                {r.description && <p style={{ fontSize: "0.82rem", marginTop: 6 }}>{r.description}</p>}
              </li>
            ))}
          </ol>
        </RevealSection>
      )}
    </div>
  );
}
