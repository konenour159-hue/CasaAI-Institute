import { useEffect, useState } from "react";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import type { AdminLearnerProgressSummary } from "../../types/api";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

export function AdminProgressPage() {
  const [rows, setRows] = useState<AdminLearnerProgressSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    adminService
      .listLearnerProgress({ search: search || undefined, limit: 50 })
      .then((page) => {
        setRows(page.items);
        setTotal(page.total);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Erreur."));
  }, [search]);

  return (
    <AdminLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <input
          placeholder="Rechercher un apprenant par nom ou email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 12px",
            fontSize: "0.9rem",
            width: 320,
          }}
        />
        <span className="mono" style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          {total} apprenant{total > 1 ? "s" : ""}
        </span>
      </div>

      {error && <p className="error-text" style={{ marginBottom: 16 }}>{error}</p>}

      {rows === null ? (
        <ListSkeleton count={5} />
      ) : rows.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)" }}>Aucun apprenant trouvé.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1.2fr 1fr 1fr 1fr 1fr",
              gap: 12,
              padding: "0 18px",
              fontSize: "0.75rem",
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.03em",
            }}
          >
            <span>Apprenant</span>
            <span>Leçons</span>
            <span>Quiz</span>
            <span>Score moyen</span>
            <span>Labs</span>
            <span>Dernière activité</span>
          </div>

          {rows.map((r, i) => (
            <RevealSection key={r.user_id} as="div" delayMs={Math.min(i, 8) * 40}>
              <Link
                to={`/admin/progress/${r.user_id}`}
                className="card"
                style={{
                  padding: "14px 18px",
                  display: "grid",
                  gridTemplateColumns: "2fr 1.2fr 1fr 1fr 1fr 1fr",
                  gap: 12,
                  alignItems: "center",
                  color: "inherit",
                }}
              >
                <div>
                  <p style={{ color: "var(--color-text)", fontWeight: 500 }}>
                    {r.first_name} {r.last_name}
                  </p>
                  <p style={{ fontSize: "0.8rem" }}>{r.email}</p>
                </div>
                <span className="mono" style={{ fontSize: "0.85rem" }}>
                  {r.lessons_completed} / {r.lessons_total_published}
                </span>
                <span className="mono" style={{ fontSize: "0.85rem" }}>
                  {r.quizzes_passed} / {r.quizzes_attempted} réussis
                </span>
                <span className="mono" style={{ fontSize: "0.85rem" }}>
                  {r.quiz_average_score !== null ? `${Math.round(r.quiz_average_score)}%` : "—"}
                </span>
                <span className="mono" style={{ fontSize: "0.85rem" }}>
                  {r.labs_completed}
                </span>
                <span style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
                  {formatDate(r.last_activity_at)}
                </span>
              </Link>
            </RevealSection>
          ))}
        </div>
      )}
    </AdminLayout>
  );
}
