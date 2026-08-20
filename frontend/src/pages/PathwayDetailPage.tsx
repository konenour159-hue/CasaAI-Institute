import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../components/AppLink";
import { RevealSection } from "../components/RevealSection";
import { CourseSkeleton } from "../components/Skeleton";
import { PathwayIcon } from "../components/ModuleIcon";
import { contentService } from "../services/contentService";
import type { PathwayDetail } from "../types/api";

export function PathwayDetailPage() {
  const { pathwayId } = useParams<{ pathwayId: string }>();
  const [pathway, setPathway] = useState<PathwayDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!pathwayId) return;
    contentService
      .getPathway(pathwayId)
      .then(setPathway)
      .catch(() => setNotFound(true));
  }, [pathwayId]);

  if (notFound) return <p className="error-text">Ce parcours est introuvable.</p>;
  if (!pathway) return <CourseSkeleton />;

  const accent = pathway.color ?? "var(--color-accent-blue)";

  return (
    <div style={{ maxWidth: 760 }}>
      <RevealSection as="div">
        <PathwayIcon color={accent} />

        <h1 style={{ fontSize: "1.9rem", marginBottom: 8 }}>{pathway.title}</h1>
        {pathway.profile_label && (
          <p style={{ color: "var(--color-text-muted)", marginBottom: 16 }}>{pathway.profile_label}</p>
        )}
        {pathway.description && (
          <p style={{ marginBottom: 40, fontSize: "1.02rem", color: "var(--color-text)" }}>{pathway.description}</p>
        )}
      </RevealSection>

      <h2 style={{ fontSize: "1.1rem", marginBottom: 16 }}>
        Cours de ce parcours{" "}
        <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>({pathway.courses.length})</span>
      </h2>

      {pathway.courses.length === 0 ? (
        <p>Aucun cours n'est encore rattaché à ce parcours.</p>
      ) : (
        <ol style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {pathway.courses.map((course, i) => (
            <RevealSection
              key={course.id}
              as="li"
              delayMs={Math.min(i, 6) * 50}
              className="card"
              style={{ padding: "18px 22px", display: "flex", alignItems: "center", gap: 18, borderLeft: `3px solid ${course.color ?? accent}` }}
            >
              <span className="mono" style={{ color: course.color ?? accent, fontSize: "0.95rem", fontWeight: 600 }}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <div style={{ flex: 1 }}>
                <p style={{ color: "var(--color-text)", fontWeight: 500, fontSize: "1rem" }}>{course.title}</p>
                {course.description && <p style={{ fontSize: "0.85rem" }}>{course.description}</p>}
              </div>
              <Link to={`/courses/${course.id}`} className="btn btn-secondary" style={{ flexShrink: 0 }}>
                Voir le cours
              </Link>
            </RevealSection>
          ))}
        </ol>
      )}
    </div>
  );
}
