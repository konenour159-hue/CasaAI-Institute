import type { CSSProperties, ReactNode } from "react";
import { useScrollReveal } from "../hooks/useScrollReveal";

interface RevealSectionProps {
  children: ReactNode;
  as?: "div" | "section" | "li";
  delayMs?: number;
  style?: CSSProperties;
  className?: string;
}

/** Enveloppe un bloc de contenu et l'anime (fondu + translation) quand il
 * entre dans le viewport au scroll — voir hooks/useScrollReveal. Utilisé
 * pour donner du rythme à une page de leçon volumineuse (objectifs,
 * sections, approfondissement, exemple). */
export function RevealSection({ children, as = "div", delayMs = 0, style, className }: RevealSectionProps) {
  const { ref, visible } = useScrollReveal();
  const Tag = as;

  return (
    <Tag
      ref={ref as never}
      className={`reveal ${visible ? "reveal-visible" : ""}${className ? ` ${className}` : ""}`}
      style={{ transitionDelay: visible ? `${delayMs}ms` : "0ms", ...style }}
    >
      {children}
    </Tag>
  );
}
