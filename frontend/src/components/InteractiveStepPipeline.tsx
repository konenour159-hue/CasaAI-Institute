import { lazy, Suspense, useEffect, useState } from "react";
import type { LabInteractiveStep } from "../types/api";
import { supportsWebGL } from "../utils/webgl";

/** Chargé à la demande uniquement (bascule 2D/3D), jamais au chargement de
 * la page — cf. PipelineScene3D.tsx. */
const PipelineScene3D = lazy(() => import("./three/PipelineScene3D"));

const NODE_W = 122;
// Zone numéro + glyphe (inchangée) puis zone de titre — élargie après
// vérification en conditions réelles sur les 8 labs : plusieurs titres
// wrappent jusqu'à 4 lignes (ex. "Construction du contexte et
// augmentation du prompt") et se faisaient couper par une zone de texte
// fixée à 30px, prévue à l'origine pour 2 lignes seulement.
const GLYPH_ZONE_H = 74;
const LABEL_ZONE_H = 58;
const NODE_H = GLYPH_ZONE_H + LABEL_ZONE_H;
const GAP = 34;
const STEP_W = NODE_W + GAP;
const TOP = 14;

/** Petit glyphe distinct par étape — donne au schéma une vraie valeur de
 * diagramme (la transformation de la donnée), pas juste une liste numérotée. */
function StepGlyph({ stepKey, color }: { stepKey: string; color: string }) {
  const stroke = color;
  switch (stepKey) {
    case "reception":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <rect x={-22} y={-14} width={44} height={28} rx={5} />
          <path d="M -22 -10 L 0 4 L 22 -10" />
        </g>
      );
    case "tokenization":
      return (
        <g>
          {[-24, -6, 12, 26].map((x, i) => (
            <rect key={i} x={x} y={-9} width={i === 3 ? 10 : 14} height={18} rx={3} fill="none" stroke={stroke} strokeWidth={1.6} />
          ))}
        </g>
      );
    case "embeddings":
      return (
        <g stroke={stroke} strokeWidth={1} fill={stroke}>
          <line x1={-24} y1={10} x2={14} y2={-14} stroke={stroke} strokeOpacity={0.35} />
          <line x1={-10} y1={16} x2={22} y2={-4} stroke={stroke} strokeOpacity={0.35} />
          <line x1={-24} y1={10} x2={-10} y2={16} stroke={stroke} strokeOpacity={0.35} />
          {[[-24, 10], [-10, 16], [14, -14], [22, -4], [4, 2], [-2, -16]].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={3.2} />
          ))}
        </g>
      );
    case "attention":
      return (
        <g stroke={stroke} strokeWidth={1.4}>
          {[-22, -22, -22].map((x, i) => (
            <rect key={i} x={x} y={-18 + i * 15} width={16} height={10} rx={2} fill="none" />
          ))}
          {[18, 18, 18].map((x, i) => (
            <rect key={i} x={x} y={-18 + i * 15} width={16} height={10} rx={2} fill="none" />
          ))}
          {[-13, -13, -13].flatMap((_, i) =>
            [0, 1, 2].map((j) => (
              <line key={`${i}-${j}`} x1={-6} y1={-13 + i * 15} x2={18} y2={-13 + j * 15} stroke={stroke} strokeOpacity={0.28} />
            ))
          )}
        </g>
      );
    case "prefill":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          {[-14, -2, 10].map((y, i) => (
            <rect key={i} x={-26} y={y} width={52 - i * 8} height={9} rx={2} />
          ))}
        </g>
      );
    case "decoding":
      return (
        <g fill={stroke}>
          {[0.3, 0.9, 0.5, 1, 0.2].map((h, i) => (
            <rect key={i} x={-26 + i * 12} y={16 - h * 30} width={8} height={h * 30} rx={1.5} opacity={i === 3 ? 1 : 0.4} />
          ))}
        </g>
      );
    case "detokenization":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M -24 -12 h 18 M -24 -2 h 30 M -24 8 h 22" />
          <path d="M 14 -14 L 26 0 L 14 14" />
        </g>
      );

    // --- Pipeline de la donnée ---------------------------------------
    case "ingestion":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M -26 -14 L -6 -4 M -26 0 L -6 -2 M -26 14 L -6 0" />
          <path d="M -6 -16 L 22 -8 L 22 8 L -6 16 Z" />
        </g>
      );
    case "transformation":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle r={13} />
          {Array.from({ length: 8 }).map((_, i) => {
            const a = (i / 8) * Math.PI * 2;
            return <line key={i} x1={Math.cos(a) * 13} y1={Math.sin(a) * 13} x2={Math.cos(a) * 18} y2={Math.sin(a) * 18} />;
          })}
        </g>
      );
    case "storage":
      return (
        <g stroke={stroke} strokeWidth={1.6}>
          <rect x={-24} y={8} width={48} height={10} rx={2} fill={stroke} opacity={0.25} />
          <rect x={-20} y={-4} width={40} height={10} rx={2} fill={stroke} opacity={0.55} />
          <rect x={-16} y={-16} width={32} height={10} rx={2} fill={stroke} opacity={0.9} />
        </g>
      );
    case "quality":
      return (
        <g stroke={stroke} strokeWidth={1.8} fill="none">
          <path d="M 0 -18 L 20 -10 V 6 C 20 16 10 22 0 24 C -10 22 -20 16 -20 6 V -10 Z" />
          <path d="M -8 0 L -2 8 L 10 -8" />
        </g>
      );
    case "catalog_governance":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <rect x={-20} y={-16} width={40} height={32} rx={3} />
          <path d="M -20 -8 h 40 M -10 -16 v 32" />
        </g>
      );
    case "serving":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <rect x={-24} y={-8} width={16} height={16} rx={3} />
          <path d="M -8 0 L 10 -12 M -8 0 L 12 0 M -8 0 L 10 12" />
          <circle cx={16} cy={-12} r={3} fill={stroke} />
          <circle cx={18} cy={0} r={3} fill={stroke} />
          <circle cx={16} cy={12} r={3} fill={stroke} />
        </g>
      );

    // --- Gouvernance des données --------------------------------------
    case "stewardship":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle cx={0} cy={-10} r={7} />
          <path d="M -14 16 C -14 2 14 2 14 16" />
          <path d="M -6 -1 L -1 5 L 8 -8" transform="translate(0, 4)" />
        </g>
      );
    case "quality_policy":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <rect x={-16} y={-20} width={32} height={40} rx={3} />
          <path d="M -8 -6 L -3 0 L 9 -12" />
          <path d="M -8 8 h 16 M -8 14 h 10" />
        </g>
      );
    case "security_privacy":
      return (
        <g stroke={stroke} strokeWidth={1.7} fill="none">
          <rect x={-14} y={-4} width={28} height={20} rx={3} />
          <path d="M -8 -4 V -12 A 8 8 0 0 1 8 -12 V -4" />
          <circle cx={0} cy={6} r={2.6} fill={stroke} />
        </g>
      );
    case "compliance":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M 0 -18 V 16 M -20 16 h 40" />
          <path d="M -20 -10 L -28 4 h 16 Z M 20 -10 L 12 4 h 16 Z" />
          <path d="M -20 -10 h 0 M 20 -10 h 0" />
          <path d="M -20 -10 L 0 -18 L 20 -10" />
        </g>
      );
    case "lineage_catalog":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle cx={-20} cy={0} r={5} />
          <circle cx={0} cy={-12} r={5} />
          <circle cx={0} cy={12} r={5} />
          <circle cx={20} cy={0} r={5} />
          <path d="M -15 0 L -4 -10 M -15 0 L -4 10 M 4 -10 L 16 -2 M 4 10 L 16 2" />
        </g>
      );

    // --- Panorama des types d'IA ---------------------------------------
    case "narrow_ai_rules":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M 0 -18 L 14 0 L 0 18 L -14 0 Z" />
          <path d="M 14 0 h 12 M -14 0 h -12" />
        </g>
      );
    case "machine_learning":
      return (
        <g stroke={stroke} strokeWidth={1.4}>
          <path d="M -22 12 L 20 -14" strokeWidth={1.8} />
          {[[-18, 6], [-8, 10], [0, -2], [10, -8], [16, 2], [-4, 4]].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={2.6} fill={stroke} stroke="none" />
          ))}
        </g>
      );
    case "deep_learning":
      return (
        <g stroke={stroke} strokeWidth={1.3} fill={stroke}>
          {[-20, 0, 20].map((x, ci) =>
            [-14, 0, 14].slice(0, ci === 1 ? 3 : 2).map((y, ri) => (
              <circle key={`${ci}-${ri}`} cx={x} cy={y - (ci === 1 ? 0 : 7)} r={3.4} />
            ))
          )}
          <g stroke={stroke} strokeOpacity={0.35}>
            <line x1={-20} y1={-14} x2={0} y2={-14} />
            <line x1={-20} y1={-14} x2={0} y2={0} />
            <line x1={-20} y1={7} x2={0} y2={-14} />
            <line x1={-20} y1={7} x2={0} y2={0} />
            <line x1={-20} y1={7} x2={0} y2={14} />
            <line x1={0} y1={-14} x2={20} y2={-7} />
            <line x1={0} y1={0} x2={20} y2={-7} />
            <line x1={0} y1={0} x2={20} y2={7} />
            <line x1={0} y1={14} x2={20} y2={7} />
          </g>
        </g>
      );
    case "transformers_llm":
      return (
        <g stroke={stroke} strokeWidth={1.4}>
          {[-18, 18].map((x) => (
            <rect key={x} x={x - 8} y={-18} width={16} height={36} rx={3} fill="none" />
          ))}
          {[-12, 0, 12].map((y) =>
            [-18, 18].map((x1) =>
              [-18, 18].map((x2) => (
                <line key={`${x1}-${x2}-${y}`} x1={x1} y1={y} x2={x2} y2={-y} stroke={stroke} strokeOpacity={0.25} />
              ))
            )
          )}
        </g>
      );
    case "generative_vs_predictive":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle cx={-16} cy={0} r={10} />
          <path d="M -16 -10 L -10 4 L -4 -14 L 2 8" transform="translate(2, 0) scale(0.7)" stroke={stroke} />
          <path d="M -6 -8 L 10 -8 M -6 4 L 10 4 M -6 12 L 4 12" transform="translate(10, 0)" />
        </g>
      );
    case "agentic_ai":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle r={7} />
          {[-1, 1].map((sx) =>
            [-1, 1].map((sy) => (
              <g key={`${sx}-${sy}`}>
                <line x1={sx * 6} y1={sy * 6} x2={sx * 20} y2={sy * 16} />
                <rect x={sx * 20 - 5} y={sy * 16 - 5} width={10} height={10} rx={2} />
              </g>
            ))
          )}
        </g>
      );

    // --- Donnée, carburant de l'IA --------------------------------------
    case "gigo":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M -22 -14 L -8 -14 L -4 14 L -18 14 Z" />
          <path d="M -8 -14 L 6 0 L -8 14" transform="translate(6,0)" />
          <path d="M 0 -8 L 10 8 M 10 -8 L 0 8" transform="translate(12,0)" />
        </g>
      );
    case "representativeness_bias":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M -24 8 L 0 -12 L 24 4" />
          <circle cx={-24} cy={8} r={3} fill={stroke} />
          <circle cx={24} cy={4} r={3} fill={stroke} />
          <path d="M 0 -12 V -18" />
          <path d="M -24 8 l -4 10 h 12 Z M 24 4 l -6 12 h 16 Z" opacity={0.5} />
        </g>
      );
    case "volume_diversity":
      return (
        <g fill={stroke}>
          {[0.4, 0.9, 0.6, 1, 0.7].map((h, i) => (
            <rect key={i} x={-26 + i * 13} y={16 - h * 32} width={9} height={h * 32} rx={2} opacity={0.4 + i * 0.12} />
          ))}
        </g>
      );
    case "training_vs_inference":
      return (
        <g stroke={stroke} strokeWidth={1.5} fill="none">
          <circle cx={-14} cy={0} r={11} />
          {Array.from({ length: 6 }).map((_, i) => {
            const a = (i / 6) * Math.PI * 2;
            return <line key={i} x1={-14 + Math.cos(a) * 11} y1={Math.sin(a) * 11} x2={-14 + Math.cos(a) * 15} y2={Math.sin(a) * 15} />;
          })}
          <path d="M 8 -16 L 0 2 L 8 2 L 2 16" fill={stroke} stroke="none" />
        </g>
      );
    case "feedback_loop":
      return (
        <g stroke={stroke} strokeWidth={1.7} fill="none">
          <path d="M -14 -14 A 18 18 0 1 1 -18 4" />
          <path d="M -24 -2 L -18 4 L -11 -4" />
          <circle cx={2} cy={-4} r={4} fill={stroke} stroke="none" />
        </g>
      );

    // --- RAG : de la question à la réponse sourcée ----------------------
    case "ingestion_chunking":
      return (
        <g stroke={stroke} strokeWidth={1.5} fill="none">
          <rect x={-24} y={-18} width={20} height={36} rx={2} />
          <path d="M -24 -6 h 20 M -24 6 h 20" strokeDasharray="2 2" />
          <path d="M 2 -10 h 20 M 2 0 h 20 M 2 10 h 14" opacity={0.6} />
        </g>
      );
    case "embedding_indexing":
      return (
        <g stroke={stroke} strokeWidth={1.5} fill="none">
          <ellipse cx={0} cy={12} rx={20} ry={6} />
          <path d="M -20 12 V -6 A 20 6 0 0 0 20 -6 V 12" />
          <path d="M -20 -6 A 20 6 0 0 0 20 -6" />
          {[[-8, -8], [4, -4], [10, 0], [-4, 2]].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={2} fill={stroke} stroke="none" />
          ))}
        </g>
      );
    case "query_retrieval":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle cx={-4} cy={-4} r={13} />
          <path d="M 6 6 L 22 22" />
          {[[-8, -8], [0, -2], [-10, 2], [2, -10]].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={1.8} fill={stroke} stroke="none" />
          ))}
        </g>
      );
    case "reranking":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          {[[-20, -12, 30], [-20, 0, 20], [-20, 12, 12]].map(([x, y, w], i) => (
            <rect key={i} x={x} y={y - 4} width={w} height={8} rx={2} fill={stroke} opacity={0.3 + i * 0.25} stroke="none" />
          ))}
          <path d="M 16 -14 L 22 -14 L 22 14 L 16 14 M 22 -14 L 16 -8 M 22 14 L 16 8" opacity={0.7} />
        </g>
      );
    case "context_building":
      return (
        <g stroke={stroke} strokeWidth={1.5} fill="none">
          <rect x={-24} y={-16} width={16} height={14} rx={2} />
          <rect x={-24} y={2} width={16} height={14} rx={2} />
          <path d="M -6 -9 h 8 M -6 9 h 8" />
          <rect x={8} y={-14} width={18} height={28} rx={3} strokeWidth={2} />
        </g>
      );
    case "grounded_generation":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M -24 -12 h 34 M -24 -2 h 34 M -24 8 h 20" />
          <path d="M 14 14 l 4 6 l 4 -6" fill={stroke} stroke="none" opacity={0.8} />
          <circle cx={18} cy={12} r={7} strokeDasharray="2 2" />
        </g>
      );

    // --- Cycle de vie MLOps -----------------------------------------------
    case "training":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle r={11} strokeDasharray="4 3" />
          <path d="M 0 -11 L 0 -16 M 8 3 L -8 3" />
          <circle cx={0} cy={3} r={2.6} fill={stroke} stroke="none" />
        </g>
      );
    case "evaluation":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle r={16} />
          <circle r={9} />
          <circle r={2.4} fill={stroke} stroke="none" />
          <path d="M 20 -20 L 2 -2" />
        </g>
      );
    case "deployment":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M 0 -18 C 10 -10 10 6 0 18 C -10 6 -10 -10 0 -18 Z" />
          <circle cx={0} cy={-4} r={3.5} />
          <path d="M -5 14 L -10 22 M 5 14 L 10 22" />
        </g>
      );
    case "monitoring":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <path d="M -24 4 h 10 l 5 -14 l 8 24 l 5 -14 l 4 4 h 8" />
        </g>
      );
    case "retraining":
      return (
        <g stroke={stroke} strokeWidth={1.7} fill="none">
          <path d="M 14 -14 A 18 18 0 1 0 18 4" />
          <path d="M 22 -2 L 18 4 L 12 -4" />
          <path d="M -3 -1 L -3 -8 L 4 -8" opacity={0.7} />
        </g>
      );

    // --- Agents IA et orchestration ----------------------------------------
    case "goal_perception":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle r={16} />
          <circle r={9} />
          <circle r={2.6} fill={stroke} stroke="none" />
        </g>
      );
    case "reasoning_planning":
      return (
        <g stroke={stroke} strokeWidth={1.5} fill="none">
          <circle cx={-20} cy={0} r={4} />
          <path d="M -16 0 h 10" />
          <path d="M -6 0 L 4 -12 M -6 0 L 4 0 M -6 0 L 4 12" />
          {[[6, -12], [6, 0], [6, 12]].map(([x, y], i) => (
            <rect key={i} x={x} y={y - 4} width={14} height={8} rx={2} />
          ))}
        </g>
      );
    case "memory":
      return (
        <g stroke={stroke} strokeWidth={1.5} fill="none">
          {[10, -2, -14].map((y, i) => (
            <ellipse key={i} cx={0} cy={y} rx={20} ry={6} opacity={1 - i * 0.15} />
          ))}
          <path d="M -20 -14 V 10 M 20 -14 V 10" />
        </g>
      );
    case "tool_use":
      return (
        <g stroke={stroke} strokeWidth={1.7} fill="none" strokeLinecap="round">
          <path d="M 6 -14 A 9 9 0 1 0 14 -6 L 4 4 L -4 -4 Z" />
          <path d="M -6 6 L -20 20 M -12 12 l -6 -6" />
        </g>
      );
    case "orchestration":
      return (
        <g stroke={stroke} strokeWidth={1.6} fill="none">
          <circle r={6} />
          {[0, 1, 2].map((i) => {
            const a = -Math.PI / 2 + (i / 3) * Math.PI * 2;
            const x = Math.cos(a) * 20;
            const y = Math.sin(a) * 20;
            return (
              <g key={i}>
                <line x1={Math.cos(a) * 6} y1={Math.sin(a) * 6} x2={x} y2={y} />
                <circle cx={x} cy={y} r={5} />
              </g>
            );
          })}
        </g>
      );
    case "governance_oversight":
      return (
        <g stroke={stroke} strokeWidth={1.7} fill="none">
          <path d="M 0 -18 L 18 -10 V 4 C 18 14 9 20 0 22 C -9 20 -18 14 -18 4 V -10 Z" />
          <path d="M -6 -10 v 12 M 6 -10 v 12 M -6 -4 h 12" opacity={0.75} />
        </g>
      );

    default:
      return <circle r={6} fill={stroke} />;
  }
}

export function InteractiveStepPipeline({ steps }: { steps: LabInteractiveStep[] }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [can3D, setCan3D] = useState(false);
  const [mode, setMode] = useState<"2d" | "3d">("2d");

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setCan3D(!reducedMotion && supportsWebGL());
  }, []);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setActiveIndex((i) => (i + 1) % steps.length);
    }, 4500);
    return () => clearInterval(id);
  }, [playing, steps.length]);

  const select = (i: number) => {
    setActiveIndex(i);
    setPlaying(false);
  };

  const active = steps[activeIndex];
  const width = steps.length * STEP_W - GAP + 40;
  const height = TOP * 2 + NODE_H;

  return (
    <div className="card" style={{ padding: 24, marginBottom: 32 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flexWrap: "wrap", gap: 10 }}>
        <h2 style={{ fontSize: "1rem" }}>Schéma interactif — étape par étape</h2>
        <div style={{ display: "flex", gap: 10 }}>
          {/* Pas de bascule proposée si la 3D ne pourrait pas s'afficher
              correctement (WebGL absent, mouvement réduit demandé) — mieux
              vaut ne rien offrir qu'un bouton qui mène à un rendu cassé. */}
          {can3D && (
            <button className="btn btn-secondary" onClick={() => setMode((m) => (m === "2d" ? "3d" : "2d"))}>
              {mode === "2d" ? "Vue 3D" : "Vue 2D"}
            </button>
          )}
          <button className="btn btn-secondary" onClick={() => setPlaying((p) => !p)}>
            {playing ? "⏸ Pause" : "▶ Lecture automatique"}
          </button>
        </div>
      </div>

      {mode === "3d" ? (
        <div style={{ height: 260, marginBottom: 24 }}>
          <Suspense
            fallback={
              <div className="skeleton" style={{ width: "100%", height: "100%", borderRadius: "var(--radius-md)" }} />
            }
          >
            <PipelineScene3D stepCount={steps.length} activeIndex={activeIndex} onSelect={select} />
          </Suspense>
        </div>
      ) : (
      <div style={{ overflowX: "auto", marginBottom: 24, paddingBottom: 8 }}>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Pipeline d'une requête, étape par étape">
          {steps.map((s, i) => {
            if (i === steps.length - 1) return null;
            const x1 = 20 + i * STEP_W + NODE_W;
            const x2 = 20 + (i + 1) * STEP_W;
            const y = TOP + NODE_H / 2;
            return (
              <g key={`arrow-${s.key}`}>
                <line x1={x1} y1={y} x2={x2 - 8} y2={y} stroke="var(--color-border)" strokeWidth={2} />
                <path d={`M ${x2 - 8} ${y - 5} L ${x2} ${y} L ${x2 - 8} ${y + 5} Z`} fill="var(--color-border)" />
              </g>
            );
          })}

          {steps.map((s, i) => {
            const x = 20 + i * STEP_W;
            const isActive = i === activeIndex;
            const color = isActive ? "var(--color-accent-blue)" : "var(--color-text-muted)";
            return (
              <g
                key={s.key}
                transform={`translate(${x}, ${TOP})`}
                onClick={() => select(i)}
                style={{ cursor: "pointer" }}
              >
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={12}
                  fill={isActive ? "var(--color-accent-blue-soft)" : "var(--color-surface-raised)"}
                  stroke={isActive ? "var(--color-accent-blue)" : "var(--color-border)"}
                  strokeWidth={isActive ? 2 : 1}
                />
                <text x={NODE_W / 2} y={18} textAnchor="middle" fontSize={10} fontFamily="var(--font-mono)" fill={color}>
                  {String(i + 1).padStart(2, "0")}
                </text>
                <g transform={`translate(${NODE_W / 2}, ${GLYPH_ZONE_H / 2 + 4})`}>
                  <StepGlyph stepKey={s.key} color={color} />
                </g>
                <foreignObject x={6} y={GLYPH_ZONE_H} width={NODE_W - 12} height={LABEL_ZONE_H}>
                  <div style={{ fontSize: "0.66rem", lineHeight: 1.2, textAlign: "center", color: isActive ? "var(--color-text)" : "var(--color-text-muted)", fontWeight: isActive ? 600 : 400 }}>
                    {s.title}
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>
      )}

      <div key={active.key} className="reveal reveal-visible">
        <span className="badge badge-gold" style={{ marginBottom: 10 }}>
          Étape {activeIndex + 1}/{steps.length}
        </span>
        <h3 style={{ fontSize: "1.15rem", marginBottom: 8 }}>{active.title}</h3>
        <p style={{ color: "var(--color-text)", marginBottom: 12, fontWeight: 500 }}>{active.summary}</p>
        <p style={{ marginBottom: 16 }}>{active.detail}</p>

        {active.highlights.length > 0 && (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
            {active.highlights.map((h) => (
              <li key={h} style={{ display: "flex", gap: 8, fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
                <span style={{ color: "var(--color-accent-teal)" }}>—</span>
                {h}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn btn-secondary" onClick={() => select(Math.max(0, activeIndex - 1))} disabled={activeIndex === 0}>
          ← Précédent
        </button>
        <button className="btn btn-secondary" onClick={() => select(Math.min(steps.length - 1, activeIndex + 1))} disabled={activeIndex === steps.length - 1}>
          Suivant →
        </button>
      </div>
    </div>
  );
}
