/** Génère un petit graphe de nœuds (façon espace d'embeddings) sur une
 * sphère — distribution déterministe (Fibonacci sphere), pas aléatoire, pour
 * une forme intentionnelle et reproductible plutôt qu'un nuage de points
 * quelconque à chaque montage. Chaque nœud est relié à ses k plus proches
 * voisins pour dessiner des arêtes plausibles. */

export interface GraphNode {
  position: [number, number, number];
  color: string;
}

export interface GraphEdge {
  from: [number, number, number];
  to: [number, number, number];
}

const ACCENTS = ["#2f63e0", "#8a6100", "#0c7a5e"]; // bleu / or / teal — mêmes tokens que index.css

function fibonacciSpherePoints(count: number, radius: number): [number, number, number][] {
  const points: [number, number, number][] = [];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2; // de 1 à -1
    const r = Math.sqrt(1 - y * y);
    const theta = goldenAngle * i;
    const x = Math.cos(theta) * r;
    const z = Math.sin(theta) * r;
    points.push([x * radius, y * radius, z * radius]);
  }
  return points;
}

function distance(a: [number, number, number], b: [number, number, number]): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

export function buildNetworkGraph(nodeCount = 16, radius = 2.2, neighborsPerNode = 2) {
  const positions = fibonacciSpherePoints(nodeCount, radius);
  const nodes: GraphNode[] = positions.map((position, i) => ({
    position,
    color: ACCENTS[i % ACCENTS.length],
  }));

  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  positions.forEach((p, i) => {
    const distances = positions
      .map((q, j) => ({ j, d: distance(p, q) }))
      .filter((x) => x.j !== i)
      .sort((a, b) => a.d - b.d)
      .slice(0, neighborsPerNode);
    distances.forEach(({ j }) => {
      const key = i < j ? `${i}-${j}` : `${j}-${i}`;
      if (!seen.has(key)) {
        seen.add(key);
        edges.push({ from: p, to: positions[j] });
      }
    });
  });

  return { nodes, edges };
}
