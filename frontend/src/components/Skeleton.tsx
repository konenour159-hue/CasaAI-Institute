import type { CSSProperties } from "react";

/** Forme d'attente animée (shimmer) réservant l'espace du contenu à venir —
 * évite le saut brutal écran-vide → contenu (cf. directive §31 Chargement).
 * `width`/`height` sont fixés une fois au montage, jamais transitionnés. */
export function Skeleton({ width = "100%", height = 16, style }: { width?: string | number; height?: number; style?: CSSProperties }) {
  return <div className="skeleton" style={{ width, height, ...style }} />;
}

/** Silhouette d'une leçon en cours de chargement : préserve approximativement
 * les dimensions du contenu réel pour que l'arrivée du texte ne déplace pas
 * la page. */
export function LessonSkeleton() {
  return (
    <div className="course-content" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Skeleton width={120} height={20} />
      <Skeleton width="80%" height={34} style={{ marginTop: 8 }} />
      <Skeleton width="60%" height={18} style={{ marginBottom: 24 }} />
      <Skeleton height={110} />
      <Skeleton height={160} />
      <Skeleton height={160} />
    </div>
  );
}

/** Silhouette d'une page de cours (titre + liste de leçons). */
export function CourseSkeleton() {
  return (
    <div className="course-content" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Skeleton width="70%" height={34} style={{ marginTop: 8 }} />
      <Skeleton width="90%" height={18} style={{ marginBottom: 24 }} />
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} height={58} />
      ))}
    </div>
  );
}

/** Silhouette d'une liste de lignes (dashboard, portfolio, listes admin). */
export function ListSkeleton({ count = 4, height = 56 }: { count?: number; height?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} height={height} />
      ))}
    </div>
  );
}

/** Silhouette d'une grille de cartes (catalogue : parcours, cours, labos). */
export function CardGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} height={132} />
      ))}
    </div>
  );
}

/** Silhouette d'un quiz en cours de chargement. */
export function QuizSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Skeleton width={160} height={14} />
      <Skeleton width="70%" height={30} style={{ marginTop: 4, marginBottom: 16 }} />
      {[0, 1].map((i) => (
        <div key={i} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Skeleton height={80} />
        </div>
      ))}
    </div>
  );
}
