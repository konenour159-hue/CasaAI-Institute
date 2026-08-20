import { buildNetworkGraph } from "./three/NetworkGraph";

/** Projection 2D du même graphe que la scène 3D (buildNetworkGraph), rendu
 * en SVG statique — utilisée quand la 3D est indisponible (WebGL absent,
 * `prefers-reduced-motion: reduce`) et comme repli le temps que le chunk
 * three.js se charge (voir HeroVisual). Aucune dépendance, aucune
 * animation : un simple dessin, cohérent avec le vocabulaire SVG déjà en
 * place ailleurs sur le site (MiniDiagram, ModuleIcon). */
export function HeroVisualStatic() {
  const { nodes, edges } = buildNetworkGraph(16, 130, 2);
  const size = 340;
  const c = size / 2;

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      height="100%"
      role="img"
      aria-label="Représentation abstraite d'un réseau de nœuds, illustrant un espace d'embeddings"
    >
      <g opacity={0.28} stroke="var(--color-text-muted)" strokeWidth={1}>
        {edges.map((edge, i) => (
          <line key={i} x1={c + edge.from[0]} y1={c + edge.from[1]} x2={c + edge.to[0]} y2={c + edge.to[1]} />
        ))}
      </g>
      {nodes.map((node, i) => (
        <circle key={i} cx={c + node.position[0]} cy={c + node.position[1]} r={5} fill={node.color} />
      ))}
    </svg>
  );
}
