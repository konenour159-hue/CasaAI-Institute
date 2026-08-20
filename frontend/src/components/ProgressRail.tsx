import { useEffect, useState } from "react";
import { useAuth } from "../stores/authStore";
import { progressService } from "../services/progressService";
import { certificationService } from "../services/certificationService";

const STAGES = [
  "Découvrir",
  "Apprendre",
  "Comprendre",
  "Expérimenter",
  "Pratiquer",
  "Évaluer",
  "Démontrer",
  "Certifier",
];

const N = STAGES.length;
const RAIL_HEIGHT = 90;
const AMPLITUDE = 11;
const CENTER_Y = RAIL_HEIGHT / 2;

/** Décalage vertical d'une étape le long du chemin — une onde, pas une
 * ligne plate, pour suggérer des "stations" plutôt qu'une simple suite
 * (cf. audit §4 point 5 "rail pédagogique en relief"). Même formule utilisée
 * ici et dans le SVG du chemin ci-dessous : les deux doivent rester en
 * phase. */
function stationOffsetY(i: number): number {
  return Math.sin(i * 0.9) * AMPLITUDE;
}

function stationXPercent(i: number): number {
  return (i / (N - 1)) * 100;
}

/** Détermine l'étape courante d'un apprenant connecté à partir de signaux
 * déjà exposés par l'API (progression de leçons, maîtrise de compétences,
 * résultats de labo, certificats de cours) — pas une valeur stockée à part,
 * mais une lecture du même état déjà utilisé par le tableau de bord.
 * Évaluée du signal le plus avancé vers le moins avancé : le premier qui
 * correspond gagne. */
async function inferCurrentStage(): Promise<number> {
  const [progress, skills, labResults, certificates] = await Promise.all([
    progressService.getMyProgress(),
    progressService.getMySkills(),
    progressService.getMyLabResults(),
    certificationService.listMyCourseCertificates(),
  ]);

  if (certificates.length > 0) return 7; // Certifier
  if (skills.some((s) => s.mastery_level >= 3)) return 6; // Démontrer
  if (skills.some((s) => s.mastery_level >= 2)) return 5; // Évaluer
  if (labResults.length > 0) return 4; // Pratiquer
  if (skills.some((s) => s.mastery_level >= 1)) return 3; // Expérimenter
  const completed = progress.filter((p) => p.status === "COMPLETED").length;
  if (completed >= 2) return 2; // Comprendre
  if (completed >= 1) return 1; // Apprendre
  return 0; // Découvrir
}

export function ProgressRail() {
  const { isAuthenticated } = useAuth();
  const [currentStage, setCurrentStage] = useState<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      setCurrentStage(null);
      return;
    }
    inferCurrentStage()
      .then(setCurrentStage)
      .catch(() => setCurrentStage(null));
  }, [isAuthenticated]);

  // Repère visuel : l'étape courante si connu, sinon l'entrée du parcours
  // (état par défaut pour un visiteur non connecté).
  const highlighted = currentStage ?? 0;

  const linePath = Array.from({ length: N }, (_, i) => {
    const x = stationXPercent(i);
    const y = CENTER_Y + stationOffsetY(i);
    return `${i === 0 ? "M" : "L"} ${x} ${y}`;
  }).join(" ");

  return (
    <div>
      <div style={{ position: "relative", height: RAIL_HEIGHT + 28 }}>
        <svg
          aria-hidden
          viewBox={`0 0 100 ${RAIL_HEIGHT}`}
          preserveAspectRatio="none"
          style={{ position: "absolute", top: 0, left: 0, width: "100%", height: RAIL_HEIGHT }}
        >
          <path d={linePath} fill="none" stroke="var(--color-border)" strokeWidth={0.4} vectorEffect="non-scaling-stroke" />
        </svg>

        <ol
          style={{
            position: "absolute",
            inset: 0,
            margin: 0,
            padding: 0,
            listStyle: "none",
          }}
        >
          {STAGES.map((stage, i) => {
            const isCurrent = i === highlighted;
            const y = CENTER_Y + stationOffsetY(i);
            const accessibleLabel = `Étape ${i + 1} sur ${N} : ${stage}${isCurrent && currentStage !== null ? " — votre étape actuelle" : ""}`;
            return (
              <li
                key={stage}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={accessibleLabel}
                style={{
                  position: "absolute",
                  left: `${stationXPercent(i)}%`,
                  top: y,
                  transform: "translate(-50%, -50%)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 8,
                  width: 84,
                }}
              >
                <div
                  aria-hidden
                  className="mono"
                  style={{
                    width: isCurrent ? 40 : 32,
                    height: isCurrent ? 40 : 32,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: isCurrent ? "0.85rem" : "0.75rem",
                    background: isCurrent ? "var(--color-accent-blue)" : "var(--color-surface-raised)",
                    color: isCurrent ? "#ffffff" : "var(--color-text-muted)",
                    border: `1px solid ${isCurrent ? "var(--color-accent-blue)" : "var(--color-border)"}`,
                    boxShadow: isCurrent ? "0 6px 18px -6px rgba(47, 99, 224, 0.45)" : "none",
                    transition: "width var(--duration-transition) var(--ease-out), height var(--duration-transition) var(--ease-out)",
                  }}
                >
                  {i + 1}
                </div>
                <span
                  aria-hidden
                  className="rail-station-label"
                  style={{
                    fontSize: "0.76rem",
                    textAlign: "center",
                    color: isCurrent ? "var(--color-text)" : "var(--color-text-muted)",
                    fontWeight: isCurrent ? 600 : 400,
                  }}
                >
                  {stage}
                </span>
                {isCurrent && currentStage !== null && (
                  <span aria-hidden className="rail-station-label text-label" style={{ color: "var(--color-accent-blue)" }}>
                    Vous en êtes là
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </div>

      <p aria-hidden className="rail-caption">
        Étape {highlighted + 1}/{N} — {STAGES[highlighted]}
      </p>
    </div>
  );
}
