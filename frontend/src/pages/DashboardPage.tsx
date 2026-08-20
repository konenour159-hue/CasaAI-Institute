import { useEffect, useState } from "react";
import { Link } from "../components/AppLink";
import { useAuth } from "../stores/authStore";
import { RevealSection } from "../components/RevealSection";
import { ListSkeleton } from "../components/Skeleton";
import { progressService } from "../services/progressService";
import type { UserLessonProgress, UserSkillProgress } from "../types/api";

export function DashboardPage() {
  const { user } = useAuth();
  const [progress, setProgress] = useState<UserLessonProgress[] | null>(null);
  const [skills, setSkills] = useState<UserSkillProgress[] | null>(null);

  useEffect(() => {
    progressService.getMyProgress().then(setProgress).catch(() => setProgress([]));
    progressService.getMySkills().then(setSkills).catch(() => setSkills([]));
  }, []);

  const completedCount = progress?.filter((p) => p.status === "COMPLETED").length ?? 0;

  return (
    <div>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.8rem", marginBottom: 4 }}>Bonjour {user?.first_name}</h1>
        <p style={{ marginBottom: 40 }}>Voici où vous en êtes dans votre apprentissage.</p>
      </RevealSection>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
        <section>
          <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>
            Progression{" "}
            <span className="mono" style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
              {completedCount} leçon{completedCount > 1 ? "s" : ""} terminée{completedCount > 1 ? "s" : ""}
            </span>
          </h2>

          {progress === null ? (
            <ListSkeleton count={3} />
          ) : progress.length === 0 ? (
            <RevealSection as="div">
              <div className="card" style={{ padding: 24 }}>
                <p style={{ marginBottom: 16 }}>
                  Vous n'avez pas encore commencé de leçon. Direction le catalogue pour trouver votre premier cours.
                </p>
                <Link to="/catalog" className="btn btn-primary">
                  Explorer le catalogue
                </Link>
              </div>
            </RevealSection>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {progress.map((p, i) => (
                <RevealSection key={p.lesson_id} as="div" delayMs={Math.min(i, 8) * 50}>
                  <Link
                    to={`/app/lessons/${p.lesson_id}`}
                    className="card"
                    style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 16 }}
                  >
                    <span
                      className="badge"
                      style={{
                        background:
                          p.status === "COMPLETED" ? "var(--color-accent-teal-soft)" : "var(--color-accent-gold-soft)",
                        color: p.status === "COMPLETED" ? "var(--color-accent-teal)" : "var(--color-accent-gold)",
                      }}
                    >
                      {p.status === "COMPLETED" ? "Terminée" : "En cours"}
                    </span>
                    <span style={{ flex: 1, color: "var(--color-text)" }}>{p.lesson_title}</span>
                  </Link>
                </RevealSection>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Compétences</h2>
          {skills === null ? (
            <ListSkeleton count={3} height={36} />
          ) : skills.length === 0 ? (
            <p style={{ fontSize: "0.9rem" }}>
              Réussissez un quiz pour commencer à faire progresser vos compétences.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {skills.map((s) => (
                <div key={s.skill_id}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem", marginBottom: 6 }}>
                    <span>{s.skill_name}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="mono" style={{ color: "var(--color-text-muted)" }}>
                        {s.mastery_level}/4
                      </span>
                      <Link to={`/app/skills/${s.skill_id}/practice`} style={{ fontSize: "0.78rem", color: "var(--color-accent-blue)" }}>
                        S'entraîner
                      </Link>
                    </div>
                  </div>
                  <div style={{ height: 6, borderRadius: 4, background: "var(--color-surface-raised)", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${(s.mastery_level / 4) * 100}%`,
                        background: "var(--color-accent-blue)",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
