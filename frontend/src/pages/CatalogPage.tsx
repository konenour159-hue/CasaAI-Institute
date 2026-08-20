import { useEffect, useState } from "react";
import { Link } from "../components/AppLink";
import { RevealSection } from "../components/RevealSection";
import { PathwayIcon, SchoolIcon } from "../components/ModuleIcon";
import { CardGridSkeleton } from "../components/Skeleton";
import { contentService } from "../services/contentService";
import type { CourseListItem, LabListItem, PathwayListItem } from "../types/api";

/** Couleurs de repli par catégorie quand l'élément n'a pas de couleur propre
 * en base — permet de distinguer visuellement les 3 sections du catalogue
 * même sans donnée color renseignée. */
const FALLBACK_ACCENT = {
  pathway: "var(--color-accent-blue)",
  course: "var(--color-accent-gold)",
  lab: "var(--color-accent-coral)",
} as const;

export function CatalogPage() {
  const [courses, setCourses] = useState<CourseListItem[] | null>(null);
  const [pathways, setPathways] = useState<PathwayListItem[] | null>(null);
  const [labs, setLabs] = useState<LabListItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([
      contentService.listCourses({ limit: 50 }),
      contentService.listPathways({ limit: 20 }),
      contentService.listLabs({ limit: 20 }),
    ])
      .then(([coursesPage, pathwaysPage, labsPage]) => {
        setCourses(coursesPage.items);
        setPathways(pathwaysPage.items);
        setLabs(labsPage.items);
      })
      .catch(() => setError(true));
  }, []);

  if (error) {
    return <p className="error-text">Impossible de charger le catalogue pour le moment.</p>;
  }

  return (
    <div>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.8rem", marginBottom: 8 }}>Catalogue</h1>
        <p style={{ marginBottom: 40 }}>Parcours et cours disponibles dès aujourd'hui.</p>
      </RevealSection>

      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: "1.15rem", marginBottom: 16 }}>Parcours</h2>
        {pathways === null ? (
          <CardGridSkeleton count={3} />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
            {pathways.map((p, i) => (
              <RevealSection key={p.id} as="div" delayMs={Math.min(i, 8) * 50} style={{ height: "100%" }}>
                <Link to={`/pathways/${p.id}`} className="card" style={{ padding: 20, display: "block", height: "100%" }}>
                  <PathwayIcon color={p.color ?? FALLBACK_ACCENT.pathway} />
                  <h3 style={{ fontSize: "1rem", marginBottom: 8 }}>{p.title}</h3>
                  <p style={{ fontSize: "0.88rem" }}>{p.description}</p>
                </Link>
              </RevealSection>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 style={{ fontSize: "1.15rem", marginBottom: 16 }}>Cours</h2>
        {courses === null ? (
          <CardGridSkeleton count={6} />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
            {courses.map((c, i) => (
              <RevealSection key={c.id} as="div" delayMs={Math.min(i, 8) * 50} style={{ height: "100%" }}>
                <Link to={`/courses/${c.id}`} className="card" style={{ padding: 20, display: "block", height: "100%" }}>
                  <SchoolIcon schoolId={c.school_id} color={c.color ?? FALLBACK_ACCENT.course} />
                  <h3 style={{ fontSize: "1rem", marginBottom: 8 }}>{c.title}</h3>
                  <p style={{ fontSize: "0.88rem" }}>{c.description}</p>
                </Link>
              </RevealSection>
            ))}
          </div>
        )}
      </section>

      <section style={{ marginTop: 48 }}>
        <h2 style={{ fontSize: "1.15rem", marginBottom: 16 }}>Laboratoires</h2>
        {labs === null ? (
          <CardGridSkeleton count={6} />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
            {labs.map((l, i) => (
              <RevealSection key={l.id} as="div" delayMs={Math.min(i, 8) * 50} style={{ height: "100%" }}>
                <Link to={`/labs/${l.id}`} className="card" style={{ padding: 20, display: "block", height: "100%" }}>
                  <SchoolIcon schoolId={l.school_id} color={l.color ?? FALLBACK_ACCENT.lab} />
                  <h3 style={{ fontSize: "1rem", marginBottom: 8 }}>{l.title}</h3>
                  <p style={{ fontSize: "0.88rem" }}>{l.description}</p>
                </Link>
              </RevealSection>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
