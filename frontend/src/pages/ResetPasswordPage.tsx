import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Link } from "../components/AppLink";
import { authService } from "../services/authService";
import { ApiError } from "../services/apiClient";
import { RevealSection } from "../components/RevealSection";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!token) {
    return (
      <div style={{ maxWidth: 400, margin: "40px auto" }}>
        <h1 style={{ fontSize: "1.6rem", marginBottom: 8 }}>Lien invalide</h1>
        <p style={{ marginBottom: 24 }}>
          Ce lien de réinitialisation est incomplet. Demandez-en un nouveau depuis la page de connexion.
        </p>
        <Link to="/forgot-password" className="btn btn-secondary">
          Demander un nouveau lien
        </Link>
      </div>
    );
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    setIsSubmitting(true);
    try {
      await authService.resetPassword({ token, new_password: newPassword });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Une erreur est survenue.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "40px auto" }}>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.6rem", marginBottom: 8 }}>Nouveau mot de passe</h1>
        <p style={{ marginBottom: 32 }}>Choisissez un nouveau mot de passe pour votre compte.</p>

        {done ? (
          <div className="card" style={{ padding: 28 }}>
            <p className="success-text" style={{ marginBottom: 16 }}>Mot de passe modifié avec succès.</p>
            <Link to="/login" className="btn btn-primary">
              Se connecter
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="field">
              <label htmlFor="new_password">Nouveau mot de passe</label>
              <input
                id="new_password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="confirm_password">Confirmer le mot de passe</label>
              <input
                id="confirm_password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>

            {error && <p className="error-text">{error}</p>}

            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Enregistrement…" : "Changer le mot de passe"}
            </button>
          </form>
        )}
      </RevealSection>
    </div>
  );
}
