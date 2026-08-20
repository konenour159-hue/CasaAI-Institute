import { useEffect, useState } from "react";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import type { AdminCertificationListItem } from "../../types/api";

export function AdminCertificationsPage() {
  const [items, setItems] = useState<AdminCertificationListItem[] | null>(null);

  useEffect(() => {
    adminService.listCertifications().then((r) => setItems(r.items));
  }, []);

  return (
    <AdminLayout>
      <h2 style={{ fontSize: "1.1rem", marginBottom: 8 }}>Certifications</h2>
      <p style={{ marginBottom: 24, fontSize: "0.88rem" }}>
        Reliez chaque critère à une compétence, un cours ou un lab pour que l'éligibilité soit vérifiée
        automatiquement à partir des quiz et de la progression réelle des apprenants.
      </p>

      {items === null ? (
        <ListSkeleton count={4} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((c, i) => (
            <RevealSection key={c.id} as="div" delayMs={Math.min(i, 8) * 40}>
              <Link
                to={`/admin/certifications/${c.id}`}
                className="card"
                style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 16 }}
              >
                <span
                  className="badge"
                  style={{
                    background: c.linked_requirement_count === c.requirement_count
                      ? "var(--color-accent-teal-soft)"
                      : "var(--color-accent-gold-soft)",
                    color: c.linked_requirement_count === c.requirement_count
                      ? "var(--color-accent-teal)"
                      : "var(--color-accent-gold)",
                  }}
                >
                  {c.linked_requirement_count}/{c.requirement_count} critères reliés
                </span>
                <div style={{ flex: 1 }}>
                  <p style={{ color: "var(--color-text)", fontWeight: 500 }}>{c.title}</p>
                  {c.level && <p style={{ fontSize: "0.8rem" }}>{c.level}</p>}
                </div>
                <span className="btn btn-secondary">Gérer les critères</span>
              </Link>
            </RevealSection>
          ))}
        </div>
      )}
    </AdminLayout>
  );
}
