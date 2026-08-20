/** Position N points le long d'un arc peu profond (courbe légère, pas un
 * cercle fermé) — garde une lecture gauche→droite pour une séquence
 * ordonnée (pipeline de labo, parcours pédagogique), contrairement à un
 * cercle qui n'a pas de sens de lecture évident sans repère supplémentaire.
 * Partagé entre PipelineScene3D et ProgressRailScene3D. */
export function arcPositions(count: number, arcHeight = 0.85): [number, number, number][] {
  const spread = Math.min(count * 1.05, 9);
  return Array.from({ length: count }, (_, i) => {
    const t = count > 1 ? i / (count - 1) : 0.5;
    const x = (t - 0.5) * spread;
    const y = Math.sin(t * Math.PI) * arcHeight;
    return [x, y, 0] as [number, number, number];
  });
}
