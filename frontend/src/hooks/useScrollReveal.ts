import { useEffect, useRef, useState } from "react";

/**
 * Révèle un élément (fondu + léger déplacement vers le haut) quand il entre
 * dans le viewport au scroll. Effet à sens unique : une fois visible, un
 * élément ne se ré-anime pas en remontant dans la page.
 *
 * `prefers-reduced-motion` est déjà géré globalement (index.css réduit les
 * durées de transition à ~0), donc aucune logique supplémentaire n'est
 * nécessaire ici pour l'accessibilité.
 */
export function useScrollReveal<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (typeof IntersectionObserver === "undefined") {
      // Environnement sans support (SSR, vieux navigateur) : on affiche
      // directement plutôt que de bloquer le contenu invisible.
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -80px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, visible };
}
