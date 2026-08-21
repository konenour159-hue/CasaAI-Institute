import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../components/AppLink";
import { RevealSection } from "../components/RevealSection";
import { MiniDiagram } from "../components/MiniDiagram";
import { Callout } from "../components/Callout";
import { LessonSkeleton } from "../components/Skeleton";
import { LessonDocumentView } from "../components/LessonDocumentView";
import { API_BASE_URL } from "../services/apiClient";
import { contentService } from "../services/contentService";
import { progressService } from "../services/progressService";
import type { CourseListItem, LessonDepthLevel, LessonDetail, LessonDocument } from "../types/api";

function resolveImageSrc(url: string): string {
  return url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
}

/** Couleurs d'accent cycliques (or / teal / corail) pour distinguer les
 * niveaux de profondeur (Essentiel, Technique, Maths, Implémentation,
 * Architecture, Gouvernance) d'un coup d'œil, sans dépendre uniquement du
 * libellé texte. */
const DEPTH_ACCENTS = ["var(--color-accent-blue)", "var(--color-accent-gold)", "var(--color-accent-teal)"];

export function LessonPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [course, setCourse] = useState<CourseListItem | null>(null);
  const [documentTree, setDocumentTree] = useState<LessonDocument | null>(null);
  const [activeDepth, setActiveDepth] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [readingProgress, setReadingProgress] = useState(0);

  useEffect(() => {
    if (!lessonId) return;
    progressService
      .getLesson(lessonId)
      .then((data) => {
        setLesson(data);
        if (data.depth_levels.length > 0) setActiveDepth(data.depth_levels[0].depth_key);
        // Fil d'Ariane : retrouver le cours parent pour répondre à
        // « où suis-je ? ». Best-effort — l'absence de titre de cours
        // n'empêche pas la lecture de la leçon.
        contentService.getCourse(data.course_id).then(setCourse).catch(() => {});
        // Structure documentaire, pour les seules leçons issues d'un import.
        // Best-effort là aussi : son absence ramène à l'affichage plat, qui
        // porte le même contenu.
        if (data.has_document) {
          progressService.getLessonDocument(lessonId).then(setDocumentTree).catch(() => {});
        }
      })
      .catch(() => setNotFound(true));
  }, [lessonId]);

  // Barre de progression de lecture : proportion de la page déjà scrollée.
  useEffect(() => {
    const handleScroll = () => {
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - doc.clientHeight;
      setReadingProgress(scrollable > 0 ? Math.min(100, (doc.scrollTop / scrollable) * 100) : 0);
    };
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleComplete = async () => {
    if (!lessonId) return;
    setCompleting(true);
    try {
      await progressService.completeLesson(lessonId);
      setCompleted(true);
    } finally {
      setCompleting(false);
    }
  };

  const depthAccentByKey = useMemo(() => {
    if (!lesson) return {};
    const map: Record<string, string> = {};
    lesson.depth_levels.forEach((d, i) => {
      map[d.depth_key] = DEPTH_ACCENTS[i % DEPTH_ACCENTS.length];
    });
    return map;
  }, [lesson]);

  if (notFound) return <p className="error-text">Cette leçon est introuvable.</p>;
  if (!lesson) return <LessonSkeleton />;

  const activeLevel: LessonDepthLevel | undefined = lesson.depth_levels.find((d) => d.depth_key === activeDepth);

  return (
    <div className="course-content">
      <div className="reading-progress-track">
        <div className="reading-progress-fill" style={{ transform: `scaleX(${readingProgress / 100})` }} />
      </div>

      {course && (
        <Link
          to={`/courses/${course.id}`}
          style={{ display: "inline-block", fontSize: "0.85rem", color: "var(--color-text-muted)", marginBottom: 14 }}
        >
          ← {course.title}
        </Link>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {lesson.level && <span className="badge badge-teal">{lesson.level}</span>}
        {lesson.duration_min && <span className="badge badge-gold">{lesson.duration_min} min</span>}
      </div>
      <h1 style={{ marginBottom: 16 }}>{lesson.title}</h1>
      {lesson.summary && (
        <p style={{ marginBottom: 24, fontSize: "1.0625rem", lineHeight: 1.7, color: "var(--color-text)" }}>
          {lesson.summary}
        </p>
      )}

      {lesson.objectives.length > 0 && (
        <RevealSection as="div">
          <Callout kind="objective">
            <ul style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 8 }}>
              {lesson.objectives.map((o, i) => (
                <li key={i} style={{ fontSize: "0.98rem" }}>
                  {o}
                </li>
              ))}
            </ul>
          </Callout>
        </RevealSection>
      )}

      {documentTree ? (
        <RevealSection as="div">
          <LessonDocumentView sections={documentTree.sections} sourceFile={documentTree.source_file} />
        </RevealSection>
      ) : lesson.sections.map((section, i) => (
        <RevealSection
          key={section.position}
          as="section"
          delayMs={Math.min(i, 4) * 60}
          className="card"
          style={{ padding: 28, marginBottom: 24 }}
        >
          <span className="lesson-section-number">
            {String(i + 1).padStart(2, "0")} / {String(lesson.sections.length).padStart(2, "0")}
          </span>
          <h2 className="lesson-section-title">{section.title}</h2>
          {section.diagram && <MiniDiagram data={section.diagram} />}
          {section.image_url && (
            <figure style={{ margin: "0 0 16px" }}>
              <img
                src={resolveImageSrc(section.image_url)}
                alt={section.image_alt ?? ""}
                style={{ maxWidth: "100%", borderRadius: "var(--radius-sm)", display: "block" }}
              />
              {section.image_alt && <figcaption className="lesson-image-caption">{section.image_alt}</figcaption>}
            </figure>
          )}
          <p className="lesson-section-body">{section.body}</p>
        </RevealSection>
      ))}

      {lesson.depth_levels.length > 0 && (
        <RevealSection as="section" style={{ marginBottom: 32 }}>
          <h2 style={{ marginBottom: 14 }}>Approfondir</h2>
          <div
            role="tablist"
            style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--color-border)", marginBottom: 20, flexWrap: "wrap" }}
          >
            {lesson.depth_levels.map((d) => {
              const isActive = activeDepth === d.depth_key;
              const accent = depthAccentByKey[d.depth_key];
              return (
                <button
                  key={d.depth_key}
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveDepth(d.depth_key)}
                  className={`depth-tab${isActive ? " active" : ""}`}
                  style={{ borderBottomColor: isActive ? accent : "transparent", color: isActive ? accent : undefined }}
                >
                  {d.label}
                </button>
              );
            })}
          </div>

          {activeLevel && (
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ marginBottom: 12 }}>{activeLevel.title}</h3>
              <p className="lesson-section-body">{activeLevel.body}</p>
            </div>
          )}
        </RevealSection>
      )}

      {lesson.example && (
        <RevealSection as="section">
          <Callout kind="example">
            <p style={{ margin: 0 }}>{lesson.example}</p>
          </Callout>
        </RevealSection>
      )}

      <button className="btn btn-primary" onClick={handleComplete} disabled={completing || completed}>
        {completed ? "Leçon terminée ✓" : completing ? "Enregistrement…" : "Marquer comme terminée"}
      </button>

      {lesson.validation_quiz_id && (
        <Link
          to={`/app/quizzes/${lesson.validation_quiz_id}`}
          className="btn btn-secondary"
          style={{ marginLeft: 12 }}
        >
          Passer le quiz de validation
        </Link>
      )}
    </div>
  );
}
