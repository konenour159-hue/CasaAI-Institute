import { lazy, Suspense, useEffect, useState } from "react";
import { HeroVisualStatic } from "./HeroVisualStatic";
import { supportsWebGL } from "../utils/webgl";

/** Composant 3D chargé dynamiquement : le code three.js/@react-three/fiber
 * n'entre dans aucun chunk chargé au démarrage, seulement quand ce module
 * est réellement importé (voir audit §5 point 4 — budget de performance). */
const HeroNetworkScene = lazy(() => import("./three/HeroNetworkScene"));

/** Visuel du Hero de la page d'accueil : scène 3D légère (réseau de nœuds,
 * façon espace d'embeddings) quand le navigateur le permet, repli statique
 * SVG sinon — jamais de canvas cassé, jamais de blocage du premier rendu.
 *
 * Trois cas font basculer sur le repli statique, sans jamais tenter de
 * charger three.js dans ces cas :
 *  - `prefers-reduced-motion: reduce` — la 3D reste une animation continue,
 *    même douce, donc concernée au même titre que le CSS (cf. §32).
 *  - Absence de support WebGL.
 *  - Pendant le chargement du chunk 3D (fallback de Suspense) — la forme
 *    finale reste ainsi visible dès le premier rendu, jamais un espace vide. */
export function HeroVisual() {
  const [canRender3D, setCanRender3D] = useState(false);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setCanRender3D(!reducedMotion && supportsWebGL());
  }, []);

  return (
    <div style={{ width: "100%", height: "100%" }}>
      {canRender3D ? (
        <Suspense fallback={<HeroVisualStatic />}>
          <HeroNetworkScene />
        </Suspense>
      ) : (
        <HeroVisualStatic />
      )}
    </div>
  );
}
