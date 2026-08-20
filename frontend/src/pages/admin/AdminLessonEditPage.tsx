import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Link } from "../../components/AppLink";
import { SectionImageField } from "../../components/SectionImageField";
import { AdminLayout } from "../../layouts/AdminLayout";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import type { AdminLessonDepthLevelInput, AdminLessonSectionInput } from "../../types/api";

const DEPTH_KEYS = ["ESSENTIAL", "TECHNICAL", "MATHEMATICS", "IMPLEMENTATION", "ARCHITECTURE", "GOVERNANCE"] as const;

export function AdminLessonEditPage() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();
  const isNew = lessonId === "new";

  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [durationMin, setDurationMin] = useState("");
  const [summary, setSummary] = useState("");
  const [example, setExample] = useState("");
  const [position, setPosition] = useState(0);
  const [status, setStatus] = useState<"DRAFT" | "PUBLISHED" | "ARCHIVED">("DRAFT");
  const [objectives, setObjectives] = useState<string[]>([]);
  const [sections, setSections] = useState<AdminLessonSectionInput[]>([]);
  const [depthLevels, setDepthLevels] = useState<AdminLessonDepthLevelInput[]>([]);

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationQuizId, setValidationQuizId] = useState<string | null>(null);

  useEffect(() => {
    if (isNew || !lessonId) return;
    adminService.getLesson(lessonId).then((l) => {
      setTitle(l.title);
      setLevel(l.level ?? "");
      setDurationMin(l.duration_min ? String(l.duration_min) : "");
      setSummary(l.summary ?? "");
      setExample(l.example ?? "");
      setPosition(l.position);
      setStatus(l.status);
      setObjectives(l.objectives);
      setSections(l.sections);
      setDepthLevels(l.depth_levels);
      setLoading(false);
    });
    adminService.listQuizzes({ lessonId }).then((res) => {
      setValidationQuizId(res.items[0]?.id ?? null);
    });
  }, [isNew, lessonId]);

  const handleSave = async () => {
    if (!courseId) return;
    setSaving(true);
    setError(null);
    const payload = {
      course_id: courseId,
      title,
      level: level || null,
      duration_min: durationMin ? Number(durationMin) : null,
      summary: summary || null,
      example: example || null,
      position,
      status,
      objectives,
      sections,
      depth_levels: depthLevels,
    };
    try {
      if (isNew) {
        await adminService.createLesson(payload);
      } else if (lessonId) {
        await adminService.updateLesson(lessonId, payload);
      }
      navigate(`/admin/courses/${courseId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <AdminLayout><ListSkeleton count={5} height={44} /></AdminLayout>;

  return (
    <AdminLayout>
      <Link to={`/admin/courses/${courseId}`} style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
        ← Retour aux leçons
      </Link>

      <h2 style={{ fontSize: "1.1rem", margin: "16px 0 24px" }}>{isNew ? "Nouvelle leçon" : "Modifier la leçon"}</h2>

      {error && <p className="error-text" style={{ marginBottom: 16 }}>{error}</p>}

      <div className="card" style={{ padding: 22, marginBottom: 20, display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="field">
          <label htmlFor="title">Titre</label>
          <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="level">Niveau</label>
            <input id="level" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="ex: N2" />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="duration">Durée (min)</label>
            <input id="duration" type="number" value={durationMin} onChange={(e) => setDurationMin(e.target.value)} />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="position">Position</label>
            <input id="position" type="number" value={position} onChange={(e) => setPosition(Number(e.target.value))} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="summary">Résumé</label>
          <input id="summary" value={summary} onChange={(e) => setSummary(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="example">Exemple</label>
          <input id="example" value={example} onChange={(e) => setExample(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="status">Statut</label>
          <select
            id="status"
            value={status}
            onChange={(e) => setStatus(e.target.value as typeof status)}
            style={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}
          >
            <option value="DRAFT">Brouillon</option>
            <option value="PUBLISHED">Publié</option>
            <option value="ARCHIVED">Archivé</option>
          </select>
        </div>
      </div>

      {/* Objectifs */}
      <div className="card" style={{ padding: 22, marginBottom: 20 }}>
        <h3 style={{ fontSize: "0.95rem", marginBottom: 14 }}>Objectifs</h3>
        {objectives.map((obj, i) => (
          <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <input
              value={obj}
              onChange={(e) => setObjectives(objectives.map((o, j) => (j === i ? e.target.value : o)))}
              style={{ flex: 1, background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}
            />
            <button className="btn btn-secondary" onClick={() => setObjectives(objectives.filter((_, j) => j !== i))}>
              ✕
            </button>
          </div>
        ))}
        <button className="btn btn-secondary" onClick={() => setObjectives([...objectives, ""])}>
          + Ajouter un objectif
        </button>
      </div>

      {/* Sections */}
      <div className="card" style={{ padding: 22, marginBottom: 20 }}>
        <h3 style={{ fontSize: "0.95rem", marginBottom: 14 }}>Sections</h3>
        {sections.map((sec, i) => (
          <div key={i} className="card" style={{ padding: 14, marginBottom: 10, background: "var(--color-surface-raised)" }}>
            <input
              placeholder="Titre de la section"
              value={sec.title}
              onChange={(e) => setSections(sections.map((s, j) => (j === i ? { ...s, title: e.target.value } : s)))}
              style={{ width: "100%", marginBottom: 8, background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}
            />
            <textarea
              placeholder="Contenu"
              rows={3}
              value={sec.body}
              onChange={(e) => setSections(sections.map((s, j) => (j === i ? { ...s, body: e.target.value } : s)))}
              style={{ width: "100%", background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px", fontFamily: "inherit", resize: "vertical" }}
            />
            <SectionImageField
              imageUrl={sec.image_url}
              imageAlt={sec.image_alt}
              onChange={(imageUrl, imageAlt) =>
                setSections(sections.map((s, j) => (j === i ? { ...s, image_url: imageUrl, image_alt: imageAlt } : s)))
              }
            />
            <button
              className="btn btn-secondary"
              onClick={() => setSections(sections.filter((_, j) => j !== i))}
              style={{ marginTop: 8 }}
            >
              Supprimer cette section
            </button>
          </div>
        ))}
        <button className="btn btn-secondary" onClick={() => setSections([...sections, { title: "", body: "" }])}>
          + Ajouter une section
        </button>
      </div>

      {/* Niveaux de profondeur */}
      <div className="card" style={{ padding: 22, marginBottom: 28 }}>
        <h3 style={{ fontSize: "0.95rem", marginBottom: 6 }}>Niveaux de profondeur</h3>
        <p style={{ fontSize: "0.82rem", marginBottom: 14 }}>
          Jusqu'à 6 niveaux (Essentiel, Technique, Mathématiques, Implémentation, Architecture, Gouvernance).
        </p>
        {depthLevels.map((dl, i) => (
          <div key={i} className="card" style={{ padding: 14, marginBottom: 10, background: "var(--color-surface-raised)" }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <select
                value={dl.depth_key}
                onChange={(e) =>
                  setDepthLevels(depthLevels.map((d, j) => (j === i ? { ...d, depth_key: e.target.value as typeof d.depth_key } : d)))
                }
                style={{ background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}
              >
                {DEPTH_KEYS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
              <input
                placeholder="Libellé (ex: Essentiel)"
                value={dl.label}
                onChange={(e) => setDepthLevels(depthLevels.map((d, j) => (j === i ? { ...d, label: e.target.value } : d)))}
                style={{ flex: 1, background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}
              />
            </div>
            <input
              placeholder="Titre"
              value={dl.title}
              onChange={(e) => setDepthLevels(depthLevels.map((d, j) => (j === i ? { ...d, title: e.target.value } : d)))}
              style={{ width: "100%", marginBottom: 8, background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}
            />
            <textarea
              placeholder="Contenu"
              rows={3}
              value={dl.body}
              onChange={(e) => setDepthLevels(depthLevels.map((d, j) => (j === i ? { ...d, body: e.target.value } : d)))}
              style={{ width: "100%", background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "8px 10px", fontFamily: "inherit", resize: "vertical" }}
            />
            <button
              className="btn btn-secondary"
              onClick={() => setDepthLevels(depthLevels.filter((_, j) => j !== i))}
              style={{ marginTop: 8 }}
            >
              Supprimer ce niveau
            </button>
          </div>
        ))}
        <button
          className="btn btn-secondary"
          onClick={() => setDepthLevels([...depthLevels, { depth_key: "ESSENTIAL", label: "", title: "", body: "" }])}
        >
          + Ajouter un niveau
        </button>
      </div>

      {!isNew && lessonId && courseId && (
        <div className="card" style={{ padding: 22, marginBottom: 28, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
          <div>
            <h3 style={{ fontSize: "0.95rem", marginBottom: 6 }}>Quiz de validation</h3>
            <p style={{ fontSize: "0.82rem" }}>
              {validationQuizId ? "Ce module a déjà un quiz de validation." : "Aucun quiz de validation pour l'instant."}
            </p>
          </div>
          <Link
            to={
              validationQuizId
                ? `/admin/quizzes/${validationQuizId}?back=${encodeURIComponent(`/admin/courses/${courseId}/lessons/${lessonId}`)}`
                : `/admin/quizzes/new?kind=VALIDATION&lesson_id=${lessonId}&back=${encodeURIComponent(`/admin/courses/${courseId}/lessons/${lessonId}`)}`
            }
            className="btn btn-secondary"
            style={{ flexShrink: 0 }}
          >
            {validationQuizId ? "Gérer le quiz" : "+ Créer un quiz"}
          </Link>
        </div>
      )}

      <button className="btn btn-primary" onClick={handleSave} disabled={saving || !title}>
        {saving ? "Enregistrement…" : "Enregistrer la leçon"}
      </button>
    </AdminLayout>
  );
}
