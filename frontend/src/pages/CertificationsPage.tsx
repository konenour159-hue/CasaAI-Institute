import { useEffect, useState } from "react";
import { Link } from "../components/AppLink";
import { certificationService } from "../services/certificationService";
import { RevealSection } from "../components/RevealSection";
import { CardGridSkeleton } from "../components/Skeleton";
import type { CertificationListItem } from "../types/api";

export function CertificationsPage() {
  const [certifications, setCertifications] = useState<CertificationListItem[] | null>(null);

  useEffect(() => {
    certificationService.list().then(setCertifications);
  }, []);

  return (
    <div>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.7rem", marginBottom: 8 }}>Certifications</h1>
        <p style={{ marginBottom: 32 }}>Des critères explicites, vérifiés à partir de votre progression réelle.</p>
      </RevealSection>

      {certifications === null ? (
        <CardGridSkeleton />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
          {certifications.map((c, i) => (
            <RevealSection key={c.id} as="div" delayMs={Math.min(i, 8) * 50} style={{ height: "100%" }}>
              <Link to={`/app/certifications/${c.id}`} className="card" style={{ padding: 22, display: "block", height: "100%" }}>
                {c.level && <span className="badge badge-gold" style={{ marginBottom: 12 }}>{c.level}</span>}
                <h2 style={{ fontSize: "1.05rem", marginBottom: 8 }}>{c.title}</h2>
                <p style={{ fontSize: "0.88rem" }}>{c.description}</p>
              </Link>
            </RevealSection>
          ))}
        </div>
      )}
    </div>
  );
}
