import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import type { AdminLearnerProgressDetail } from "../../types/api";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

const STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: "Non commencée",
  IN_PROGRESS: "En cours",
  COMPLETED: "Terminée",
};

export function AdminLearnerProgressDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const [detail, setDetail] = useState<AdminLearnerProgressDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    setError(null);
    adminService
      .getLearnerProgressDetail(userId)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : "Erreur."));
  }, [userId]);

  return (
    <AdminLayout>
      <Link to="/admin/progress" style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
        ← Retour à la liste
      </Link>

      {error && <p className="error-text" style={{ marginTop: 16 }}>{error}</p>}

      {!detail ? (
        !error && <ListSkeleton count={4} height={44} />
      ) : (
        <RevealSection as="div">
          <div style={{ margin: "20px 0 32px" }}>
            <h2 style={{ fontSize: "1.3rem" }}>
              {detail.first_name} {detail.last_name}
            </h2>
            <p style={{ fontSize: "0.9rem" }}>{detail.email}</p>
          </div>

          <section style={{ marginBottom: 32 }}>
            <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>Leçons</h3>
            {detail.lessons.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>Aucune progression enregistrée.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {detail.lessons.map((l, i) => (
                  <RevealSection key={l.lesson_id} as="div" delayMs={Math.min(i, 8) * 30}>
                    <div
                      className="card"
                      style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 16 }}
                    >
                      <span style={{ flex: 1 }}>{l.lesson_title}</span>
                      <span className="mono" style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                        {l.progress_pct}%
                      </span>
                      <span className="badge">{STATUS_LABELS[l.status] ?? l.status}</span>
                      <span style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", width: 100, textAlign: "right" }}>
                        {formatDate(l.completed_at)}
                      </span>
                    </div>
                  </RevealSection>
                ))}
              </div>
            )}
          </section>

          <section style={{ marginBottom: 32 }}>
            <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>Tentatives de quiz</h3>
            {detail.quiz_attempts.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>Aucune tentative enregistrée.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {detail.quiz_attempts.map((q, i) => (
                  <RevealSection key={q.attempt_id} as="div" delayMs={Math.min(i, 8) * 30}>
                    <div
                      className="card"
                      style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 16 }}
                    >
                      <span style={{ flex: 1 }}>{q.quiz_title}</span>
                      <span className="mono" style={{ fontSize: "0.8rem" }}>{q.score}%</span>
                      <span
                        className="badge"
                        style={{
                          background: q.passed ? "var(--color-accent-teal-soft)" : "var(--color-accent-coral-soft)",
                          color: q.passed ? "var(--color-accent-teal)" : "var(--color-accent-coral)",
                        }}
                      >
                        {q.passed ? "Réussi" : "Échoué"}
                      </span>
                      <span style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", width: 100, textAlign: "right" }}>
                        {formatDate(q.started_at)}
                      </span>
                    </div>
                  </RevealSection>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>Labs</h3>
            {detail.lab_results.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>Aucun résultat enregistré.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {detail.lab_results.map((r, i) => (
                  <RevealSection key={r.result_id} as="div" delayMs={Math.min(i, 8) * 30}>
                    <div
                      className="card"
                      style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 16 }}
                    >
                      <span style={{ flex: 1 }}>{r.lab_title}</span>
                      <span className="mono" style={{ fontSize: "0.8rem" }}>
                        {r.score !== null ? `${r.score}%` : "—"}
                      </span>
                      <span className="badge">{r.completed ? "Terminé" : "En cours"}</span>
                      <span style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", width: 100, textAlign: "right" }}>
                        {formatDate(r.submitted_at)}
                      </span>
                    </div>
                  </RevealSection>
                ))}
              </div>
            )}
          </section>
        </RevealSection>
      )}
    </AdminLayout>
  );
}
