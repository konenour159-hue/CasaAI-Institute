import { useRef, useState } from "react";
import { adminService } from "../services/adminService";
import { API_BASE_URL } from "../services/apiClient";

interface SectionImageFieldProps {
  imageUrl: string | null | undefined;
  imageAlt: string | null | undefined;
  onChange: (imageUrl: string | null, imageAlt: string | null) => void;
}

/** Résout une URL d'image renvoyée par l'API (relative, ex: /media/sections/xxx.png)
 * vers une URL absolue pointant sur le backend — nécessaire car le frontend
 * (Vite, port 5173) et le backend (port 8000) sont des origines différentes. */
function resolveImageSrc(url: string): string {
  return url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
}

const MAX_SIZE_MB = 5;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

/** Champ "image de section" : bouton d'import, aperçu, texte alternatif,
 * suppression. Utilisé à côté de chaque section de texte dans l'éditeur de
 * leçon (formulaire admin « Ajouter un cours »). */
export function SectionImageField({ imageUrl, imageAlt, onChange }: SectionImageFieldProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // permet de resélectionner le même fichier après une erreur
    if (!file) return;

    setError(null);

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError("Format non supporté (JPEG, PNG, WEBP ou GIF attendu).");
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Fichier trop volumineux (max ${MAX_SIZE_MB} Mo).`);
      return;
    }

    setUploading(true);
    try {
      const result = await adminService.uploadSectionImage(file);
      onChange(result.url, imageAlt ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'import de l'image.");
    } finally {
      setUploading(false);
    }
  };

  if (imageUrl) {
    return (
      <div style={{ display: "flex", gap: 10, marginTop: 8, alignItems: "flex-start" }}>
        <img
          src={resolveImageSrc(imageUrl)}
          alt={imageAlt ?? ""}
          style={{ width: 96, height: 96, objectFit: "cover", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-border)", flexShrink: 0 }}
        />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
          <input
            placeholder="Texte alternatif (accessibilité)"
            value={imageAlt ?? ""}
            onChange={(e) => onChange(imageUrl, e.target.value)}
            style={{ background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", padding: "6px 8px", fontSize: "0.85rem" }}
          />
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => onChange(null, null)}
            style={{ alignSelf: "flex-start", fontSize: "0.8rem", padding: "4px 10px" }}
          >
            Retirer l'image
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 8 }}>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        onChange={handleFileSelected}
        style={{ display: "none" }}
      />
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        style={{ fontSize: "0.82rem" }}
      >
        {uploading ? "Import en cours…" : "+ Importer une image"}
      </button>
      {error && <p className="error-text" style={{ fontSize: "0.8rem", marginTop: 6 }}>{error}</p>}
    </div>
  );
}
