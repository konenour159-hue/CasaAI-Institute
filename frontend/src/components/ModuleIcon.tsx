/** Badge visuel par module (parcours/cours/lab) — remplace les anciens badges
 * niveau/durée retirés de l'affichage. Les cours et labs sont rattachés à une
 * école (school_id) : on en tire une icône thématique. Les parcours n'ont pas
 * d'école propre (ils traversent plusieurs écoles) : icône générique dédiée. */
import type { ReactNode } from "react";

function IconBadge({ color, children }: { color: string; children: ReactNode }) {
  return (
    <div
      style={{
        width: 44,
        height: 44,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: `${color}26`,
        marginBottom: 14,
        flexShrink: 0,
      }}
    >
      <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </div>
  );
}

const SCHOOL_GLYPHS: Record<string, ReactNode> = {
  agents: (
    <>
      <rect x={5} y={7} width={14} height={12} rx={3} />
      <path d="M12 7V3" />
      <circle cx={12} cy={2} r={1} fill="currentColor" stroke="none" />
      <circle cx={9} cy={13} r={1.2} fill="currentColor" stroke="none" />
      <circle cx={15} cy={13} r={1.2} fill="currentColor" stroke="none" />
      <path d="M9 17h6" />
    </>
  ),
  culture: (
    <>
      <path d="M4 5.5C4 4.7 4.7 4 5.5 4H12v16H5.5A1.5 1.5 0 0 1 4 18.5z" />
      <path d="M20 5.5C20 4.7 19.3 4 18.5 4H12v16h6.5a1.5 1.5 0 0 0 1.5-1.5z" />
    </>
  ),
  data: (
    <>
      <ellipse cx={12} cy={5.5} rx={7} ry={2.5} />
      <path d="M5 5.5V18.5C5 19.9 8.1 21 12 21C15.9 21 19 19.9 19 18.5V5.5" />
      <path d="M5 12C5 13.4 8.1 14.5 12 14.5C15.9 14.5 19 13.4 19 12" />
    </>
  ),
  deep: (
    <>
      <circle cx={6} cy={7} r={2} />
      <circle cx={6} cy={17} r={2} />
      <circle cx={18} cy={12} r={2} />
      <path d="M8 7.6L16 11 M8 16.4L16 13" />
    </>
  ),
  genai: (
    <>
      <path d="M12 3 L13.7 9.3 20 11 13.7 12.7 12 19 10.3 12.7 4 11 10.3 9.3 Z" />
    </>
  ),
  governance: (
    <>
      <path d="M12 3v18M6 21h12" />
      <path d="M5 7 2.5 12a2.5 2.5 0 0 0 5 0z" />
      <path d="M19 7l-2.5 5a2.5 2.5 0 0 0 5 0z" />
      <path d="M5 7h14" />
    </>
  ),
  math: <path d="M17 5H7l5 7-5 7h10" />,
  ml: (
    <>
      <path d="M4 18L20 6" strokeWidth={1.9} />
      <circle cx={6} cy={16} r={1.4} fill="currentColor" stroke="none" />
      <circle cx={11} cy={11.5} r={1.4} fill="currentColor" stroke="none" />
      <circle cx={16} cy={8} r={1.4} fill="currentColor" stroke="none" />
    </>
  ),
  rag: (
    <>
      <rect x={4} y={3} width={11} height={15} rx={1.5} />
      <path d="M7 7h5M7 10.5h5M7 14h3" />
      <circle cx={16.5} cy={16.5} r={3.2} />
      <path d="M18.8 18.8L21 21" />
    </>
  ),
  security: <path d="M12 3 20 6.5V12c0 4.6-3.2 8-8 9-4.8-1-8-4.4-8-9V6.5z" />,
  software: <path d="M8 6 3 12l5 6M16 6l5 6-5 6M13.5 4l-3 16" />,
  systems: (
    <>
      <rect x={4} y={4} width={16} height={5} rx={1.5} />
      <rect x={4} y={10.5} width={16} height={5} rx={1.5} />
      <rect x={4} y={17} width={16} height={3.5} rx={1.5} />
      <circle cx={7} cy={6.5} r={0.7} fill="currentColor" stroke="none" />
      <circle cx={7} cy={13} r={0.7} fill="currentColor" stroke="none" />
    </>
  ),
  usecases: (
    <>
      <circle cx={12} cy={12} r={8} />
      <circle cx={12} cy={12} r={4} />
      <circle cx={12} cy={12} r={0.8} fill="currentColor" stroke="none" />
    </>
  ),
};

const FALLBACK_GLYPH = (
  <>
    <circle cx={12} cy={12} r={8} />
    <path d="M12 8v5M12 16h.01" />
  </>
);

const PATHWAY_GLYPH = (
  <>
    <path d="M4 19c3-1 3-5 6-6s3 4 6 3 3-6 4-6" strokeDasharray="0.5 3.2" />
    <circle cx={4} cy={19} r={1.3} fill="currentColor" stroke="none" />
    <path d="M18 6 20.5 5 19.5 8Z" fill="currentColor" stroke="none" />
  </>
);

export function SchoolIcon({ schoolId, color }: { schoolId: string | null | undefined; color: string }) {
  return <IconBadge color={color}>{(schoolId && SCHOOL_GLYPHS[schoolId]) ?? FALLBACK_GLYPH}</IconBadge>;
}

export function PathwayIcon({ color }: { color: string }) {
  return <IconBadge color={color}>{PATHWAY_GLYPH}</IconBadge>;
}
