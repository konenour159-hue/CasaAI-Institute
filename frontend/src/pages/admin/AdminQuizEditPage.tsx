import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import type { AdminQuestionInput, ContentStatus, QuizKind } from "../../types/api";

const KIND_LABELS: Record<QuizKind, string> = {
  PRACTICE: "Entraînement (rattaché à une compétence)",
  VALIDATION: "Validation (rattaché à une leçon)",
  FINAL: "Final (rattaché à un cours)",
};

function emptyQuestion(): AdminQuestionInput {
  return { question_text: "", explanation: "", difficulty: 1, options: [{ option_text: "", is_correct: true }, { option_text: "", is_correct: false }] };
}

export function AdminQuizEditPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isNew = quizId === "new";

  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<QuizKind>((searchParams.get("kind") as QuizKind) || "PRACTICE");
  const [lessonId, setLessonId] = useState(searchParams.get("lesson_id") ?? "");
  const [courseId, setCourseId] = useState(searchParams.get("course_id") ?? "");
  const [skillId, setSkillId] = useState(searchParams.get("skill_id") ?? "");
  const [passThreshold, setPassThreshold] = useState(70);
  const [status, setStatus] = useState<ContentStatus>("DRAFT");
  const [questions, setQuestions] = useState<AdminQuestionInput[]>([]);

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const backTo = searchParams.get("back") || "/admin/courses";

  useEffect(() => {
    if (isNew || !quizId) return;
    adminService.getQuiz(quizId).then((q) => {
      setTitle(q.title);
      setKind(q.kind);
      setLessonId(q.lesson_id ?? "");
      setCourseId(q.course_id ?? "");
      setSkillId(q.skill_id ?? "");
      setPassThreshold(q.pass_threshold);
      setStatus(q.status);
      setQuestions(
        q.questions.map((qq) => ({
          question_text: qq.question_text,
          explanation: qq.explanation,
          difficulty: qq.difficulty,
          options: qq.options.map((o) => ({ option_text: o.option_text, is_correct: o.is_correct })),
        })),
      );
      setLoading(false);
    });
  }, [isNew, quizId]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    const payload = {
      title,
      kind,
      lesson_id: kind === "VALIDATION" ? lessonId || null : null,
      course_id: kind === "FINAL" ? courseId || null : null,
      skill_id: kind === "PRACTICE" ? skillId || null : null,
      pass_threshold: passThreshold,
      status,
      questions,
    };
    try {
      if (isNew) {
        await adminService.createQuiz(payload);
      } else if (quizId) {
        await adminService.updateQuiz(quizId, payload);
      }
      navigate(backTo);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!quizId || isNew) return;
    if (!confirm("Supprimer ce quiz et toutes ses questions ?")) return;
    setSaving(true);
    try {
      await adminService.deleteQuiz(quizId);
      navigate(backTo);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
      setSaving(false);
    }
  };

  const updateQuestion = (i: number, patch: Partial<AdminQuestionInput>) =>
    setQuestions(questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));

  const setCorrectOption = (qi: number, oi: number) =>
    setQuestions(
      questions.map((q, j) =>
        j === qi ? { ...q, options: q.options.map((o, k) => ({ ...o, is_correct: k === oi })) } : q,
      ),
    );

  if (loading) return <AdminLayout><ListSkeleton count={5} height={44} /></AdminLayout>;

  return (
    <AdminLayout>
      <Link to={backTo} style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
        ← Retour
      </Link>

      <h2 style={{ fontSize: "1.1rem", margin: "16px 0 24px" }}>{isNew ? "Nouveau quiz" : "Modifier le quiz"}</h2>

      {error && <p className="error-text" style={{ marginBottom: 16 }}>{error}</p>}

      <div className="card" style={{ padding: 22, marginBottom: 20, display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="field">
          <label htmlFor="title">Titre</label>
          <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="kind">Type</label>
            <select
              id="kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as QuizKind)}
              disabled={!isNew}
              style={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}
            >
              {Object.entries(KIND_LABELS).map(([k, label]) => (
                <option key={k} value={k}>{label}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="pass">Seuil de réussite (%)</label>
            <input id="pass" type="number" min={0} max={100} value={passThreshold} onChange={(e) => setPassThreshold(Number(e.target.value))} />
          </div>
        </div>

        {kind === "VALIDATION" && (
          <div className="field">
            <label htmlFor="lesson_id">ID de la leçon</label>
            <input id="lesson_id" value={lessonId} onChange={(e) => setLessonId(e.target.value)} disabled={!isNew} />
          </div>
        )}
        {kind === "FINAL" && (
          <div className="field">
            <label htmlFor="course_id">ID du cours</label>
            <input id="course_id" value={courseId} onChange={(e) => setCourseId(e.target.value)} disabled={!isNew} />
          </div>
        )}
        {kind === "PRACTICE" && (
          <div className="field">
            <label htmlFor="skill_id">ID de la compétence</label>
            <input id="skill_id" value={skillId} onChange={(e) => setSkillId(e.target.value)} disabled={!isNew} />
          </div>
        )}

        <div className="field">
          <label htmlFor="status">Statut</label>
          <select
            id="status"
            value={status}
            onChange={(e) => setStatus(e.target.value as ContentStatus)}
            style={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}
          >
            <option value="DRAFT">Brouillon</option>
            <option value="PUBLISHED">Publié</option>
            <option value="ARCHIVED">Archivé</option>
          </select>
          {status !== "PUBLISHED" && (
            <p style={{ fontSize: "0.78rem", marginTop: 6, color: "var(--color-text-muted)" }}>
              Un quiz non publié reste invisible pour les apprenants, même si un bouton y mène.
            </p>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: 22, marginBottom: 28 }}>
        <h3 style={{ fontSize: "0.95rem", marginBottom: 14 }}>
          Questions <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>({questions.length})</span>
        </h3>

        {questions.map((q, qi) => (
          <div key={qi} className="card" style={{ padding: 16, marginBottom: 12, background: "var(--color-surface-raised)" }}>
            <textarea
              placeholder="Énoncé de la question"
              rows={2}
              value={q.question_text}
              onChange={(e) => updateQuestion(qi, { question_text: e.target.value })}
              style={{ width: "100%", marginBottom: 10, background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px", fontFamily: "inherit", resize: "vertical" }}
            />

            <p style={{ fontSize: "0.78rem", marginBottom: 6, color: "var(--color-text-muted)" }}>
              Options — sélectionnez la bonne réponse
            </p>
            {q.options.map((opt, oi) => (
              <div key={oi} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <input
                  type="radio"
                  name={`correct-${qi}`}
                  checked={opt.is_correct}
                  onChange={() => setCorrectOption(qi, oi)}
                />
                <input
                  value={opt.option_text}
                  placeholder={`Option ${oi + 1}`}
                  onChange={(e) =>
                    updateQuestion(qi, {
                      options: q.options.map((o, k) => (k === oi ? { ...o, option_text: e.target.value } : o)),
                    })
                  }
                  style={{ flex: 1, background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "6px 10px" }}
                />
                {q.options.length > 2 && (
                  <button
                    className="btn btn-secondary"
                    onClick={() => updateQuestion(qi, { options: q.options.filter((_, k) => k !== oi) })}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            <button
              className="btn btn-secondary"
              onClick={() => updateQuestion(qi, { options: [...q.options, { option_text: "", is_correct: false }] })}
              style={{ fontSize: "0.8rem", marginBottom: 10 }}
            >
              + Ajouter une option
            </button>

            <input
              placeholder="Explication (optionnelle, affichée après réponse)"
              value={q.explanation ?? ""}
              onChange={(e) => updateQuestion(qi, { explanation: e.target.value })}
              style={{ width: "100%", marginBottom: 10, background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}
            />

            <button
              className="btn btn-secondary"
              onClick={() => setQuestions(questions.filter((_, j) => j !== qi))}
              style={{ color: "var(--color-accent-coral)" }}
            >
              Supprimer cette question
            </button>
          </div>
        ))}

        <button className="btn btn-secondary" onClick={() => setQuestions([...questions, emptyQuestion()])}>
          + Ajouter une question
        </button>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving || !title}>
          {saving ? "Enregistrement…" : "Enregistrer le quiz"}
        </button>
        {!isNew && (
          <button className="btn btn-secondary" onClick={handleDelete} disabled={saving} style={{ color: "var(--color-accent-coral)" }}>
            Supprimer le quiz
          </button>
        )}
      </div>
    </AdminLayout>
  );
}
