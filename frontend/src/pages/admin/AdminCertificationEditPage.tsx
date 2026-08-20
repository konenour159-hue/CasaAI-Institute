import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import type { AdminCertification, AdminCertificationRequirement, AdminCertificationRequirementType } from "../../types/api";

const TYPE_LABELS: Record<AdminCertificationRequirementType, string> = {
  COURSE: "Cours terminé",
  MIN_SCORE: "Score minimum sur un quiz de compétence",
  LAB: "Lab complété",
  SKILL: "Maîtrise de compétence",
  EVIDENCE: "Preuve libre (revue manuelle)",
  FINAL_PROJECT: "Projet final (revue manuelle)",
};

// Champ de référence attendu par type — cf. app/services/admin_certification_service.py
const REFERENCE_FIELD: Partial<Record<AdminCertificationRequirementType, "course_id" | "lab_id" | "skill_id">> = {
  COURSE: "course_id",
  LAB: "lab_id",
  SKILL: "skill_id",
  MIN_SCORE: "skill_id",
};

export function AdminCertificationEditPage() {
  const { certificationId } = useParams<{ certificationId: string }>();
  const [cert, setCert] = useState<AdminCertification | null>(null);
  const [drafts, setDrafts] = useState<Record<string, AdminCertificationRequirement>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [savedId, setSavedId] = useState<string | null>(null);

  const load = () => {
    if (!certificationId) return;
    adminService.getCertification(certificationId).then((c) => {
      setCert(c);
      setDrafts(Object.fromEntries(c.requirements.map((r) => [r.id, r])));
    });
  };

  useEffect(load, [certificationId]);

  const updateDraft = (id: string, patch: Partial<AdminCertificationRequirement>) =>
    setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

  const handleSave = async (requirementId: string) => {
    if (!certificationId) return;
    const draft = drafts[requirementId];
    setSavingId(requirementId);
    setErrors((e) => ({ ...e, [requirementId]: "" }));
    setSavedId(null);
    try {
      const updated = await adminService.updateCertificationRequirement(certificationId, requirementId, {
        requirement_type: draft.requirement_type,
        description: draft.description,
        course_id: draft.course_id || null,
        lab_id: draft.lab_id || null,
        skill_id: draft.skill_id || null,
        min_score: draft.min_score,
      });
      setDrafts((d) => ({ ...d, [requirementId]: updated }));
      setSavedId(requirementId);
    } catch (e) {
      setErrors((err) => ({ ...err, [requirementId]: e instanceof Error ? e.message : "Erreur." }));
    } finally {
      setSavingId(null);
    }
  };

  if (!cert) return <AdminLayout><ListSkeleton count={3} height={140} /></AdminLayout>;

  return (
    <AdminLayout>
      <Link to="/admin/certifications" style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
        ← Retour
      </Link>

      <h2 style={{ fontSize: "1.1rem", margin: "16px 0 4px" }}>{cert.title}</h2>
      <p style={{ marginBottom: 24, fontSize: "0.85rem" }}>{cert.description}</p>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {cert.requirements.map((original, i) => {
          const draft = drafts[original.id] ?? original;
          const refField = REFERENCE_FIELD[draft.requirement_type];
          return (
            <RevealSection key={original.id} as="div" delayMs={Math.min(i, 8) * 50}>
            <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ fontWeight: 500 }}>{original.description || "(sans description)"}</p>

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <div className="field" style={{ flex: 1, minWidth: 220 }}>
                  <label>Type</label>
                  <select
                    value={draft.requirement_type}
                    onChange={(e) => updateDraft(original.id, { requirement_type: e.target.value as AdminCertificationRequirementType })}
                    style={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "10px 12px", width: "100%" }}
                  >
                    {Object.entries(TYPE_LABELS).map(([t, label]) => (
                      <option key={t} value={t}>{label}</option>
                    ))}
                  </select>
                </div>

                {refField && (
                  <div className="field" style={{ flex: 1, minWidth: 200 }}>
                    <label>
                      {refField === "course_id" ? "ID du cours" : refField === "lab_id" ? "ID du lab" : "ID de la compétence"}
                    </label>
                    <input
                      value={draft[refField] ?? ""}
                      onChange={(e) => updateDraft(original.id, { [refField]: e.target.value } as Partial<AdminCertificationRequirement>)}
                      placeholder={refField === "skill_id" ? "ex: ai-literacy" : refField === "course_id" ? "ex: agents-panorama" : "ex: rag-red-team"}
                    />
                  </div>
                )}

                {draft.requirement_type === "MIN_SCORE" && (
                  <div className="field" style={{ width: 140 }}>
                    <label>Score minimum (%)</label>
                    <input
                      type="number" min={0} max={100}
                      value={draft.min_score ?? ""}
                      onChange={(e) => updateDraft(original.id, { min_score: e.target.value === "" ? null : Number(e.target.value) })}
                    />
                  </div>
                )}
              </div>

              {(draft.requirement_type === "EVIDENCE" || draft.requirement_type === "FINAL_PROJECT") && (
                <p style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>
                  Ce type de critère reste évalué manuellement — aucune référence à un quiz ou une compétence ne
                  peut le rendre automatique.
                </p>
              )}

              {errors[original.id] && <p className="error-text" style={{ fontSize: "0.85rem" }}>{errors[original.id]}</p>}

              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <button className="btn btn-primary" onClick={() => handleSave(original.id)} disabled={savingId === original.id}>
                  {savingId === original.id ? "Enregistrement…" : "Enregistrer"}
                </button>
                {savedId === original.id && (
                  <span style={{ fontSize: "0.8rem", color: "var(--color-accent-teal)" }}>Enregistré.</span>
                )}
              </div>
            </div>
            </RevealSection>
          );
        })}
      </div>
    </AdminLayout>
  );
}
