import { useEffect, useState, type FormEvent } from "react";
import { contentService } from "../services/contentService";
import { portfolioService } from "../services/portfolioService";
import { RevealSection } from "../components/RevealSection";
import { ListSkeleton } from "../components/Skeleton";
import type { PortfolioEvidence, Skill } from "../types/api";

export function PortfolioPage() {
  const [evidence, setEvidence] = useState<PortfolioEvidence[] | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [showForm, setShowForm] = useState(false);

  const refresh = () => portfolioService.listMine().then(setEvidence);

  useEffect(() => {
    refresh();
    contentService.listSkills().then(setSkills);
  }, []);

  return (
    <div style={{ maxWidth: 760 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: "1.7rem", marginBottom: 8 }}>Mon portfolio</h1>
          <p>Des preuves concrètes de vos compétences — pas seulement des cours terminés.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Annuler" : "Ajouter une preuve"}
        </button>
      </div>

      {showForm && (
        <EvidenceForm
          skills={skills}
          onCreated={() => {
            setShowForm(false);
            refresh();
          }}
        />
      )}

      {evidence === null ? (
        <ListSkeleton count={3} height={100} />
      ) : evidence.length === 0 ? (
        <RevealSection as="div">
          <div className="card" style={{ padding: 24 }}>
            <p>Aucune preuve pour l'instant. Ajoutez la première à partir d'un projet ou d'un lab réel.</p>
          </div>
        </RevealSection>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {evidence.map((e, i) => (
            <RevealSection key={e.id} as="div" delayMs={Math.min(i, 8) * 50}>
              <div className="card" style={{ padding: 22 }}>
                <h2 style={{ fontSize: "1.05rem", marginBottom: 10 }}>{e.title}</h2>
                {e.context && <p style={{ marginBottom: 8, fontSize: "0.9rem" }}>{e.context}</p>}
                {e.result && (
                  <p style={{ fontSize: "0.88rem", color: "var(--color-accent-teal)", marginBottom: 10 }}>
                    Résultat : {e.result}
                  </p>
                )}
                {e.skill_ids.length > 0 && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {e.skill_ids.map((sid) => (
                      <span key={sid} className="badge badge-teal">
                        {sid}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </RevealSection>
          ))}
        </div>
      )}
    </div>
  );
}

function EvidenceForm({ skills, onCreated }: { skills: Skill[]; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [context, setContext] = useState("");
  const [problem, setProblem] = useState("");
  const [role, setRole] = useState("");
  const [deliverable, setDeliverable] = useState("");
  const [result, setResult] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const toggleSkill = (id: string) => {
    setSelectedSkills((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await portfolioService.create({
        title,
        context: context || undefined,
        problem: problem || undefined,
        role: role || undefined,
        deliverable: deliverable || undefined,
        result: result || undefined,
        skill_ids: selectedSkills,
      });
      onCreated();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card" style={{ padding: 24, marginBottom: 32, display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="field">
        <label htmlFor="title">Titre</label>
        <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="context">Contexte</label>
        <input id="context" value={context} onChange={(e) => setContext(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="problem">Problème</label>
        <input id="problem" value={problem} onChange={(e) => setProblem(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="role">Votre rôle</label>
        <input id="role" value={role} onChange={(e) => setRole(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="deliverable">Livrable</label>
        <input id="deliverable" value={deliverable} onChange={(e) => setDeliverable(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="result">Résultat</label>
        <input id="result" value={result} onChange={(e) => setResult(e.target.value)} />
      </div>

      <div className="field">
        <label>Compétences démontrées</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 140, overflowY: "auto", padding: 4 }}>
          {skills.map((s) => (
            <button
              type="button"
              key={s.id}
              onClick={() => toggleSkill(s.id)}
              className="badge"
              style={{
                cursor: "pointer",
                border: "1px solid var(--color-border)",
                background: selectedSkills.includes(s.id) ? "var(--color-accent-blue-soft)" : "transparent",
                color: selectedSkills.includes(s.id) ? "var(--color-accent-blue)" : "var(--color-text-muted)",
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>

      <button type="submit" className="btn btn-primary" disabled={submitting || !title}>
        {submitting ? "Enregistrement…" : "Enregistrer la preuve"}
      </button>
    </form>
  );
}
