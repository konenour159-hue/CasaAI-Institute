import { useEffect, useState, type FormEvent } from "react";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import { contentService } from "../../services/contentService";
import type { AdminCourse, School } from "../../types/api";

export function AdminCoursesPage() {
  const [courses, setCourses] = useState<AdminCourse[] | null>(null);
  const [schools, setSchools] = useState<School[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => adminService.listCourses({ limit: 100 }).then((p) => setCourses(p.items));

  useEffect(() => {
    refresh();
    contentService.listSchools().then(setSchools);
  }, []);

  const handlePublishToggle = async (course: AdminCourse) => {
    setError(null);
    try {
      await adminService.updateCourse(course.id, {
        ...course,
        status: course.status === "PUBLISHED" ? "DRAFT" : "PUBLISHED",
      });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  };

  const handleDelete = async (course: AdminCourse) => {
    if (!confirm(`Supprimer le cours "${course.title}" et toutes ses leçons ?`)) return;
    setError(null);
    try {
      await adminService.deleteCourse(course.id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  };

  return (
    <AdminLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h2 style={{ fontSize: "1.1rem" }}>Cours</h2>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Annuler" : "Nouveau cours"}
        </button>
      </div>

      {error && <p className="error-text" style={{ marginBottom: 16 }}>{error}</p>}

      {showForm && (
        <CourseCreateForm
          schools={schools}
          onCreated={() => {
            setShowForm(false);
            refresh();
          }}
        />
      )}

      {courses === null ? (
        <ListSkeleton count={4} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {courses.map((c, i) => (
            <RevealSection key={c.id} as="div" delayMs={Math.min(i, 8) * 40}>
              <div className="card" style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 16 }}>
                <span
                  className="badge"
                  style={{
                    background: c.status === "PUBLISHED" ? "var(--color-accent-teal-soft)" : "var(--color-accent-gold-soft)",
                    color: c.status === "PUBLISHED" ? "var(--color-accent-teal)" : "var(--color-accent-gold)",
                  }}
                >
                  {c.status}
                </span>
                <div style={{ flex: 1 }}>
                  <p style={{ color: "var(--color-text)", fontWeight: 500 }}>{c.title}</p>
                  <p style={{ fontSize: "0.8rem" }}>{c.school_id}</p>
                </div>
                <Link to={`/admin/courses/${c.id}`} className="btn btn-secondary">
                  Gérer les leçons
                </Link>
                <button className="btn btn-secondary" onClick={() => handlePublishToggle(c)}>
                  {c.status === "PUBLISHED" ? "Dépublier" : "Publier"}
                </button>
                <button className="btn btn-secondary" onClick={() => handleDelete(c)} style={{ color: "var(--color-accent-coral)" }}>
                  Supprimer
                </button>
              </div>
            </RevealSection>
          ))}
        </div>
      )}
    </AdminLayout>
  );
}

function CourseCreateForm({ schools, onCreated }: { schools: School[]; onCreated: () => void }) {
  const [schoolId, setSchoolId] = useState(schools[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!schoolId && schools.length > 0) setSchoolId(schools[0].id);
  }, [schools, schoolId]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await adminService.createCourse({
        school_id: schoolId, title, level: level || null, description: description || null, status: "DRAFT",
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card" style={{ padding: 22, marginBottom: 28, display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="field">
        <label htmlFor="school">École</label>
        <select
          id="school"
          value={schoolId}
          onChange={(e) => setSchoolId(e.target.value)}
          style={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}
        >
          {schools.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="title">Titre</label>
        <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="level">Niveau (optionnel)</label>
        <input id="level" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="ex: N1" />
      </div>
      <div className="field">
        <label htmlFor="description">Description</label>
        <input id="description" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      {error && <p className="error-text">{error}</p>}
      <button type="submit" className="btn btn-primary" disabled={submitting || !title || !schoolId}>
        {submitting ? "Création…" : "Créer le cours (brouillon)"}
      </button>
    </form>
  );
}
