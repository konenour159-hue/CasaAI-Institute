import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { BufferGeometry, Float32BufferAttribute, type Group, type Mesh } from "three";
import { arcPositions } from "./arcLayout";

function Edge({ from, to }: { from: [number, number, number]; to: [number, number, number] }) {
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new Float32BufferAttribute([...from, ...to], 3));
    return g;
  }, [from, to]);

  return (
    <line>
      <primitive object={geometry} attach="geometry" />
      <lineBasicMaterial attach="material" color="#8891a8" transparent opacity={0.4} />
    </line>
  );
}

function StageNode({ position, active, phase }: { position: [number, number, number]; active: boolean; phase: number }) {
  const mesh = useRef<Mesh>(null);
  const [x, y, z] = position;

  useFrame(({ clock }) => {
    if (!mesh.current) return;
    mesh.current.position.y = y + Math.sin(clock.elapsedTime * 0.8 + phase) * 0.06;
  });

  const radius = active ? 0.22 : 0.13;
  const color = active ? "#2f63e0" : "#8891a8";

  return (
    <mesh ref={mesh} position={[x, y, z]}>
      <sphereGeometry args={[radius, 24, 24]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={active ? 0.75 : 0.12} roughness={0.35} />
    </mesh>
  );
}

/** Même vocabulaire de mouvement que le hero et le schéma 3D des labos —
 * suit mollement le pointeur, aucun contrôle utilisateur. Contrairement au
 * schéma de labo, purement informatif : ni clic ni sélection, comme la
 * version 2D du rail (seule l'étape courante se distingue des autres,
 * aucune interaction n'existe déjà à reproduire). */
function RotatingRail({ count, activeIndex }: { count: number; activeIndex: number }) {
  const group = useRef<Group>(null);
  const positions = useMemo(() => arcPositions(count), [count]);
  const pointer = useThree((state) => state.pointer);

  useFrame(() => {
    if (!group.current) return;
    const targetX = pointer.y * 0.08;
    const targetY = pointer.x * 0.12;
    group.current.rotation.x += (targetX - group.current.rotation.x) * 0.04;
    group.current.rotation.y += (targetY - group.current.rotation.y) * 0.04;
  });

  return (
    <group ref={group}>
      {positions.slice(0, -1).map((p, i) => (
        <Edge key={i} from={p} to={positions[i + 1]} />
      ))}
      {positions.map((p, i) => (
        <StageNode key={i} position={p} active={i === activeIndex} phase={i * 0.6} />
      ))}
    </group>
  );
}

interface ProgressRailScene3DProps {
  stageCount: number;
  activeIndex: number;
}

/** Chargé dynamiquement par ProgressRail — jamais importé statiquement
 * ailleurs (cf. PipelineScene3D.tsx, même principe). */
export default function ProgressRailScene3D({ stageCount, activeIndex }: ProgressRailScene3DProps) {
  return (
    <Canvas
      camera={{ position: [0, 0.3, 5.5], fov: 42 }}
      gl={{ alpha: true, antialias: true }}
      dpr={[1, 1.5]}
      style={{ width: "100%", height: "100%" }}
    >
      <ambientLight intensity={0.6} />
      <pointLight position={[3, 4, 5]} intensity={35} color="#ffffff" />
      <RotatingRail count={stageCount} activeIndex={activeIndex} />
    </Canvas>
  );
}
