import type { ReactNode } from "react";

type CalloutKind = "objective" | "example" | "definition" | "important" | "tip" | "warning" | "takeaway";

const LABELS: Record<CalloutKind, string> = {
  objective: "Objectif d'apprentissage",
  example: "Exemple",
  definition: "Définition",
  important: "Important",
  tip: "Astuce",
  warning: "Attention",
  takeaway: "À retenir",
};

const ICONS: Record<CalloutKind, string> = {
  objective: "→",
  example: "▸",
  definition: "§",
  important: "!",
  tip: "✦",
  warning: "⚠",
  takeaway: "✓",
};

/** Bloc pédagogique discret (bordure + fond teinté, pas une carte à ombre) —
 * sert à faire ressortir un objectif, un exemple ou une notion clé sans
 * transformer toute la leçon en suite de cartes (cf. directive §11). */
export function Callout({ kind, label, children }: { kind: CalloutKind; label?: string; children: ReactNode }) {
  return (
    <div className={`callout callout-${kind}`}>
      <div className="callout-label">
        <span aria-hidden style={{ fontSize: "0.85rem" }}>
          {ICONS[kind]}
        </span>
        <span className="text-label">{label ?? LABELS[kind]}</span>
      </div>
      <div className="callout-body">{children}</div>
    </div>
  );
}
