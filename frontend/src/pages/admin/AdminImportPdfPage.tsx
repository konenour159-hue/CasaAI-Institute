import { useEffect, useState, type FormEvent } from "react";
import { Link } from "../../components/AppLink";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { adminService } from "../../services/adminService";
import { contentService } from "../../services/contentService";
import type {
  PdfImportResult,
  PdfPreviewResult,
  PdfPreviewSection,
  School,
} from "../../types/api";

/** Libellés des natures de bloc produites par le moteur d'import. */
const BLOCK_LABELS: Record<string, string> = {
  TEXT: "texte",
  LIST: "liste",
  CODE: "code",
  TABLE: "tableau",
  FORMULA: "formule",
  CAPTION: "légende",
};

function countBlocks(sections: PdfPreviewSection[]): number {
  return sections.reduce(
    (total, section) => total + section.blocks.length + countBlocks(section.children),
    0,
  );
}

/** Une branche de l'arbre. Les sections de premier niveau restent ouvertes :
 *  c'est la vue d'ensemble que l'on vient chercher avant de valider. */
function SectionNode({ section, depth }: { section: PdfPreviewSection; depth: number }) {
  const [open, setOpen] = useState(depth === 0);
  const hasChildren = section.children.length > 0 || section.blocks.length > 0;
  const uncertain = section.confidence < 0.6;

  return (
    <li style={{ listStyle: "none", marginLeft: depth === 0 ? 0 : 18 }}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        disabled={!hasChildren}
        style={{
          background: "none",
          border: "none",
          padding: "3px 0",
          cursor: hasChildren ? "pointer" : "default",
          color: "var(--color-text)",
          fontWeight: depth === 0 ? 600 : 400,
          textAlign: "left",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span style={{ opacity: hasChildren ? 0.7 : 0.2, fontSize: "0.75rem" }}>
          {hasChildren ? (open ? "▼" : "▶") : "•"}
        </span>
        <span>{section.title}</span>
        {uncertain && (
          <span className="badge" title="Titre incertain — à relire">
            à vérifier
          </span>
        )}
      </button>

      {open && (
        <ul style={{ margin: 0, padding: 0 }}>
          {section.blocks.map((block, index) => (
            <li
              key={index}
              style={{
                listStyle: "none",
                marginLeft: 24,
                padding: "2px 0",
                fontSize: "0.85rem",
                opacity: 0.75,
              }}
            >
              <span style={{ opacity: 0.6 }}>
                {BLOCK_LABELS[block.kind] ?? block.kind.toLowerCase()} —{" "}
              </span>
              {block.preview}
              {block.preview.length >= 160 && "…"}
            </li>
          ))}
          {section.children.map((child) => (
            <SectionNode key={child.title + child.level} section={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function AdminImportPdfPage() {
  const [schools, setSchools] = useState<School[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [createCourse, setCreateCourse] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [preview, setPreview] = useState<PdfPreviewResult | null>(null);
  const [result, setResult] = useState<PdfImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    contentService.listSchools().then((s) => {
      setSchools(s);
      if (s.length > 0) setSchoolId(s[0].id);
    });
  }, []);

  const chooseFile = (chosen: File | null) => {
    setFile(chosen);
    setPreview(null);
    setResult(null);
    setError(null);
  };

  const handleAnalyze = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setAnalyzing(true);
    setError(null);
    try {
      setPreview(await adminService.previewPdf(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'analyse.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleImport = async () => {
    if (!file || !schoolId) return;
    setImporting(true);
    setError(null);
    try {
      setResult(await adminService.importPdf(file, schoolId, createCourse));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'import.");
    } finally {
      setImporting(false);
    }
  };

  const report = preview?.report;
  const scanned = report?.document_type === "SCANNED";

  return (
    <AdminLayout>
      <div style={{ maxWidth: 720 }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: 8 }}>Importer un cours depuis un PDF</h2>
        <p style={{ marginBottom: 24 }}>
          Le document est d'abord analysé sans rien enregistrer : sections, blocs et points à
          vérifier s'affichent avant que quoi que ce soit ne soit créé.
        </p>

        <form
          onSubmit={handleAnalyze}
          className="card"
          style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}
        >
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
              onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={!createCourse}
              onChange={(e) => setCreateCourse(!e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              Document de référence uniquement
              <br />
              <span style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                Le document rejoint le corpus documentaire sans créer de cours à relire et
                publier. À cocher pour un ouvrage entier, qui n'a pas vocation à devenir une
                leçon.
              </span>
            </span>
          </label>

          {error && <p className="error-text">{error}</p>}

          <button type="submit" className="btn btn-primary" disabled={analyzing || !file || !!result}>
            {analyzing ? "Analyse en cours…" : "Analyser"}
          </button>
        </form>

        {preview && !result && (
          <RevealSection as="div">
            <div className="card" style={{ padding: 22, marginTop: 24 }}>
              <span className="badge" style={{ marginBottom: 12 }}>Prévisualisation</span>
              <p style={{ marginBottom: 14 }}>
                <strong style={{ color: "var(--color-text)" }}>{preview.title}</strong> —{" "}
                {preview.pages} page{preview.pages > 1 ? "s" : ""} analysée
                {preview.pages > 1 ? "s" : ""}
              </p>

              {scanned && (
                <p className="error-text" style={{ marginBottom: 14 }}>
                  Ce PDF est probablement scanné : presque aucun texte n'a pu être extrait.
                  L'OCR n'est pas pris en charge, l'import produirait une leçon vide.
                </p>
              )}

              {report && (
                <ul
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                    gap: 10,
                    margin: "0 0 16px",
                    padding: 0,
                    listStyle: "none",
                  }}
                >
                  {[
                    ["sections", report.sections],
                    ["sous-sections", report.subsections],
                    ["blocs", report.blocks],
                    ["listes", report.lists],
                    ["tableaux", report.tables],
                    ["formules", report.formulas],
                    ["blocs de code", report.code_blocks],
                    ["légendes", report.captions],
                  ]
                    .filter(([, value]) => (value as number) > 0)
                    .map(([label, value]) => (
                      <li key={label as string}>
                        <strong style={{ color: "var(--color-text)", fontSize: "1.15rem" }}>{value}</strong>
                        <br />
                        <span style={{ fontSize: "0.85rem", opacity: 0.75 }}>{label}</span>
                      </li>
                    ))}
                </ul>
              )}

              {report && report.anomalies.length > 0 && (
                <details style={{ marginBottom: 16 }}>
                  <summary style={{ cursor: "pointer" }}>
                    {report.anomalies.length} élément
                    {report.anomalies.length > 1 ? "s nécessitent" : " nécessite"} une vérification
                  </summary>
                  <ul style={{ margin: "10px 0 0 18px", fontSize: "0.88rem", opacity: 0.85 }}>
                    {report.anomalies.map((anomaly, index) => (
                      <li key={index} style={{ marginBottom: 4 }}>
                        {anomaly.page !== null && (
                          <span style={{ opacity: 0.6 }}>p. {anomaly.page + 1} — </span>
                        )}
                        {anomaly.message}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              {preview.sections.length > 0 ? (
                <>
                  <h3 style={{ fontSize: "0.95rem", marginBottom: 8 }}>Structure</h3>
                  <ul style={{ margin: "0 0 20px", padding: 0 }}>
                    {preview.sections.map((section) => (
                      <SectionNode key={section.title + section.level} section={section} depth={0} />
                    ))}
                  </ul>
                </>
              ) : (
                <p style={{ marginBottom: 20, opacity: 0.8 }}>
                  Aucune section n'a pu être reconstruite : le contenu sera importé d'un seul tenant.
                </p>
              )}

              <div style={{ display: "flex", gap: 10 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleImport}
                  disabled={importing || !schoolId}
                >
                  {importing
                    ? "Import en cours…"
                    : createCourse
                      ? "Valider et importer"
                      : "Verser au corpus"}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => chooseFile(null)}>
                  Choisir un autre fichier
                </button>
              </div>
              <p style={{ fontSize: "0.82rem", opacity: 0.7, marginTop: 10, marginBottom: 0 }}>
                Rien n'a encore été enregistré.{" "}
                {createCourse
                  ? "Le cours sera créé en brouillon, à relire avant publication"
                  : "Aucun cours ne sera créé"}{" "}
                — {countBlocks(preview.sections)} bloc
                {countBlocks(preview.sections) > 1 ? "s" : ""} seront écrits.
              </p>
            </div>
          </RevealSection>
        )}

        {result && (
          <RevealSection as="div">
            <div className="card" style={{ padding: 22, marginTop: 24, borderColor: "var(--color-accent-teal)" }}>
              <span className="badge badge-teal" style={{ marginBottom: 12 }}>Import réussi</span>
              <p style={{ marginBottom: 6 }}>
                <strong style={{ color: "var(--color-text)" }}>{result.title}</strong> — {result.pages_extracted} page{result.pages_extracted > 1 ? "s" : ""} extraite{result.pages_extracted > 1 ? "s" : ""}
              </p>
              {result.warning && <p className="error-text" style={{ marginBottom: 10 }}>{result.warning}</p>}
              {result.course_id ? (
                <Link to={`/admin/courses/${result.course_id}`} className="btn btn-secondary">
                  Relire et publier
                </Link>
              ) : (
                <p style={{ marginBottom: 0, opacity: 0.8 }}>
                  Versé au corpus documentaire. Aucun cours n'a été créé.
                </p>
              )}
            </div>
          </RevealSection>
        )}
      </div>
    </AdminLayout>
  );
}
