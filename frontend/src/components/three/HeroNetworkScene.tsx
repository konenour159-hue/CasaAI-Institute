import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { BufferGeometry, Float32BufferAttribute, type Group, type Mesh } from "three";
import { buildNetworkGraph } from "./NetworkGraph";

/** Segment de ligne entre deux nœuds — implémenté directement avec
 * `<line>`/bufferGeometry plutôt que le helper `Line` de @react-three/drei :
 * évite d'ajouter toute la dépendance drei (~150 Kb gzip à elle seule) pour
 * un simple trait. */
function Edge({ from, to }: { from: [number, number, number]; to: [number, number, number] }) {
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new Float32BufferAttribute([...from, ...to], 3));
    return g;
  }, [from, to]);

  return (
    <line>
      <primitive object={geometry} attach="geometry" />
      <lineBasicMaterial attach="material" color="#8891a8" transparent opacity={0.35} />
    </line>
  );
}

/** Nœud flottant : léger mouvement vertical sinusoïdal, déphasé par index
 * plutôt qu'une amplitude identique partout — évite l'effet "respiration
 * synchronisée" qui trahirait une boucle générique. Remplace le helper
 * `Float` de drei pour la même raison de budget que pour les arêtes. */
function Node({ position, color, phase }: { position: [number, number, number]; color: string; phase: number }) {
  const mesh = useRef<Mesh>(null);
  const [x, y, z] = position;

  useFrame(({ clock }) => {
    if (!mesh.current) return;
    mesh.current.position.y = y + Math.sin(clock.elapsedTime * 0.9 + phase) * 0.08;
  });

  return (
    <mesh ref={mesh} position={[x, y, z]}>
      <sphereGeometry args={[0.09, 16, 16]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.55} roughness={0.35} />
    </mesh>
  );
}

/** Le groupe entier tourne très lentement et suit mollement le pointeur —
 * jamais de contrôle utilisateur (pas d'OrbitControls) : c'est un élément de
 * contemplation, pas un jouet à manipuler (cf. audit §3 "réservée aux
 * moments de contemplation"). */
function RotatingGraph() {
  const group = useRef<Group>(null);
  const { nodes, edges } = useMemo(() => buildNetworkGraph(16, 2.2, 2), []);
  const pointer = useThree((state) => state.pointer);

  useFrame((_, delta) => {
    if (!group.current) return;
    group.current.rotation.y += delta * 0.08;
    // Parallax léger : la cible suit le pointeur, atteinte progressivement
    // (lerp) pour rester douce plutôt que de "coller" à la souris.
    const targetX = pointer.y * 0.15;
    const targetY = pointer.x * 0.15;
    group.current.rotation.x += (targetX - group.current.rotation.x) * 0.04;
    group.current.rotation.z += (targetY - group.current.rotation.z) * 0.04 * 0.3;
  });

  return (
    <group ref={group}>
      {edges.map((edge, i) => (
        <Edge key={i} from={edge.from} to={edge.to} />
      ))}
      {nodes.map((node, i) => (
        <Node key={i} position={node.position} color={node.color} phase={i * 0.7} />
      ))}
    </group>
  );
}

/** Scène complète (canvas + lumières + graphe). Composant chargé
 * dynamiquement par HeroVisual — ne jamais l'importer statiquement ailleurs,
 * sous peine de faire entrer three.js dans le chunk initial. */
export default function HeroNetworkScene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 42 }}
      gl={{ alpha: true, antialias: true }}
      dpr={[1, 1.5]}
      style={{ width: "100%", height: "100%" }}
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[4, 4, 4]} intensity={40} color="#f2f1f8" />
      <RotatingGraph />
    </Canvas>
  );
}
