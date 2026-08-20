import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../components/AppLink";
import { useAuth } from "../stores/authStore";
import { contentService } from "../services/contentService";
import { progressService } from "../services/progressService";
import { InteractiveStepPipeline } from "../components/InteractiveStepPipeline";
import { SchoolIcon } from "../components/ModuleIcon";
import { RevealSection } from "../components/RevealSection";
import { CourseSkeleton } from "../components/Skeleton";
import type { LabDetail, LabResult } from "../types/api";

export function LabDetailPage() {
  const { labId } = useParams<{ labId: string }>();
  const { isAuthenticated } = useAuth();
  const [lab, setLab] = useState<LabDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [mode, setMode] = useState("");
  const [submissionText, setSubmissionText] = useState("");
  const [score, setScore] = useState(70);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<LabResult | null>(null);

  useEffect(() => {
    if (!labId) return;
    contentService
      .getLab(labId)
      .then((data) => {
        setLab(data);
        if (data.modes.length > 0) setMode(data.modes[0]);
      })
      .catch(() => setNotFound(true));
  }, [labId]);

  if (notFound) return <p className="error-text">Ce lab est introuvable.</p>;
  if (!lab) return <CourseSkeleton />;

  const handleSubmit = async () => {
    if (!labId) return;
    setSubmitting(true);
    try {
      const res = await progressService.submitLab(labId, {
        mode: mode || undefined,
        submission: submissionText ? { texte: submissionText } : undefined,
        score,
      });
      setResult(res);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 720 }}>
      <RevealSection as="div">
        <SchoolIcon schoolId={lab.school_id} color={lab.color ?? "var(--color-accent-coral)"} />
        <h1 style={{ fontSize: "1.7rem", marginBottom: 16 }}>{lab.title}</h1>
        <p style={{ marginBottom: 32 }}>{lab.description}</p>
      </RevealSection>

      {lab.skills.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 32 }}>
          {lab.skills.map((s) => (
            <span key={s} className="badge badge-teal">
              {s}
            </span>
          ))}
        </div>
      )}

      {lab.interactive_steps && lab.interactive_steps.length > 0 && (
        <InteractiveStepPipeline steps={lab.interactive_steps} />
      )}

      {[
        ["Environnement", lab.environment],
        ["Instructions", lab.instructions],
        ["Données", lab.dataset_ref],
        ["Travail demandé", lab.deliverable],
        ["Critères d'évaluation", lab.evaluation_note],
      ].map(([title, body]) =>
        body ? (
          <section key={title} style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: "1rem", marginBottom: 8 }}>{title}</h2>
            <p>{body}</p>
          </section>
        ) : null
      )}

      <hr style={{ border: "none", borderTop: "1px solid var(--color-border)", margin: "32px 0" }} />

      {!isAuthenticated ? (
        <div className="card" style={{ padding: 24 }}>
          <p style={{ marginBottom: 16 }}>Connectez-vous pour soumettre votre travail sur ce lab.</p>
          <Link to="/login" className="btn btn-primary">
            Se connecter
          </Link>
        </div>
      ) : result ? (
        <div className="card" style={{ padding: 24, borderColor: "var(--color-accent-teal)" }}>
          <span className="badge badge-teal" style={{ marginBottom: 12 }}>
            Soumission enregistrée
          </span>
          <p>Votre travail a bien été soumis pour évaluation.</p>
        </div>
      ) : (
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: 20 }}>Soumettre mon travail</h2>

          {lab.modes.length > 0 && (
            <div className="field" style={{ marginBottom: 16 }}>
              <label htmlFor="mode">Mode</label>
              <select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                style={{
                  background: "var(--color-surface-raised)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  padding: "10px 12px",
                }}
              >
                {lab.modes.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="field" style={{ marginBottom: 16 }}>
            <label htmlFor="submission">Votre livrable (lien, résumé, notes…)</label>
            <textarea
              id="submission"
              rows={5}
              value={submissionText}
              onChange={(e) => setSubmissionText(e.target.value)}
              style={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: 12,
                fontFamily: "inherit",
                fontSize: "0.9rem",
                resize: "vertical",
              }}
            />
          </div>

          <div className="field" style={{ marginBottom: 20 }}>
            <label htmlFor="score">Auto-évaluation ({score}/100)</label>
            <input
              id="score"
              type="range"
              min={0}
              max={100}
              value={score}
              onChange={(e) => setScore(Number(e.target.value))}
            />
          </div>

          <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Envoi…" : "Soumettre"}
          </button>
        </div>
      )}
    </div>
  );
}
