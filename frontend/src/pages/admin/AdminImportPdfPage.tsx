import { useEffect, useState, type FormEvent } from "react";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { adminService } from "../../services/adminService";
import { contentService } from "../../services/contentService";
import type { PdfImportResult, School } from "../../types/api";

export function AdminImportPdfPage() {
  const [schools, setSchools] = useState<School[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<PdfImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    contentService.listSchools().then((s) => {
      setSchools(s);
      if (s.length > 0) setSchoolId(s[0].id);
    });
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || !schoolId) return;
    setImporting(true);
    setError(null);
    setResult(null);
    try {
      const res = await adminService.importPdf(file, schoolId);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'import.");
    } finally {
      setImporting(false);
    }
  };

  return (
    <AdminLayout>
      <div style={{ maxWidth: 560 }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: 8 }}>Importer un cours depuis un PDF</h2>
        <p style={{ marginBottom: 24 }}>
          Le texte est extrait page par page et déposé en brouillon — une relecture et une mise en forme
          restent nécessaires avant publication.
        </p>

        <form onSubmit={handleSubmit} className="card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="field">
            <label htmlFor="school">École de rattachement</label>
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
            <label htmlFor="file">Fichier PDF</label>
            <input
              id="file"
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {error && <p className="error-text">{error}</p>}

          <button type="submit" className="btn btn-primary" disabled={importing || !file || !schoolId}>
            {importing ? "Import en cours…" : "Importer"}
          </button>
        </form>

        {result && (
          <RevealSection as="div">
            <div className="card" style={{ padding: 22, marginTop: 24, borderColor: "var(--color-accent-teal)" }}>
              <span className="badge badge-teal" style={{ marginBottom: 12 }}>Import réussi</span>
              <p style={{ marginBottom: 6 }}>
                <strong style={{ color: "var(--color-text)" }}>{result.title}</strong> — {result.pages_extracted} page{result.pages_extracted > 1 ? "s" : ""} extraite{result.pages_extracted > 1 ? "s" : ""}
              </p>
              {result.warning && <p className="error-text" style={{ marginBottom: 10 }}>{result.warning}</p>}
              <Link to={`/admin/courses/${result.course_id}`} className="btn btn-secondary">
                Relire et publier
              </Link>
            </div>
          </RevealSection>
        )}
      </div>
    </AdminLayout>
  );
}
