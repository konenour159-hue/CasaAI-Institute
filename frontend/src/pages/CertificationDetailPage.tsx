import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { certificationService } from "../services/certificationService";
import { RevealSection } from "../components/RevealSection";
import { CourseSkeleton } from "../components/Skeleton";
import type { CertificationDetail, CertificationEligibility } from "../types/api";

function StatusIcon({ satisfied }: { satisfied: boolean | null }) {
  if (satisfied === true) {
    return <span style={{ color: "var(--color-accent-teal)" }}>✓</span>;
  }
  if (satisfied === false) {
    return <span style={{ color: "var(--color-accent-coral)" }}>✗</span>;
  }
  return <span style={{ color: "var(--color-accent-gold)" }}>?</span>;
}

export function CertificationDetailPage() {
  const { certificationId } = useParams<{ certificationId: string }>();
  const [cert, setCert] = useState<CertificationDetail | null>(null);
  const [eligibility, setEligibility] = useState<CertificationEligibility | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!certificationId) return;
    certificationService.get(certificationId).then(setCert).catch(() => setNotFound(true));
    certificationService.getMyEligibility(certificationId).then(setEligibility);
  }, [certificationId]);

  if (notFound) return <p className="error-text">Cette certification est introuvable.</p>;
  if (!cert) return <CourseSkeleton />;

  return (
    <div style={{ maxWidth: 680 }}>
      <RevealSection as="div">
        {cert.level && <span className="badge badge-gold" style={{ marginBottom: 16 }}>{cert.level}</span>}
        <h1 style={{ fontSize: "1.7rem", marginBottom: 16 }}>{cert.title}</h1>
        <p style={{ marginBottom: 32 }}>{cert.description}</p>

        {eligibility && (
          <div
            className="card"
            style={{
              padding: 22,
              marginBottom: 32,
              borderColor: eligibility.eligible ? "var(--color-accent-teal)" : "var(--color-border)",
            }}
          >
            <span
              className="badge"
              style={{
                background: eligibility.eligible ? "var(--color-accent-teal-soft)" : "var(--color-accent-gold-soft)",
                color: eligibility.eligible ? "var(--color-accent-teal)" : "var(--color-accent-gold)",
              }}
            >
              {eligibility.eligible ? "Conditions remplies" : "Conditions non encore remplies"}
            </span>
          </div>
        )}
      </RevealSection>

      <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Critères</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {cert.requirements.map((req, i) => {
          const status = eligibility?.requirements.find((r) => r.requirement_id === req.id);
          return (
            <RevealSection key={req.id} as="div" delayMs={Math.min(i, 8) * 50}>
              <div className="card" style={{ padding: 16, display: "flex", gap: 14, alignItems: "flex-start" }}>
                <span className="mono" style={{ fontSize: "1rem", minWidth: 16, textAlign: "center" }}>
                  {status ? <StatusIcon satisfied={status.satisfied} /> : "…"}
                </span>
                <div>
                  <p style={{ color: "var(--color-text)", fontSize: "0.9rem", marginBottom: status?.detail ? 4 : 0 }}>
                    {req.description ?? req.requirement_type}
                  </p>
                  {status && (
                    <p style={{ fontSize: "0.8rem" }}>
                      {status.satisfied === null ? "Revue manuelle nécessaire — " : ""}
                      {status.detail}
                    </p>
                  )}
                </div>
              </div>
            </RevealSection>
          );
        })}
      </div>
    </div>
  );
}
