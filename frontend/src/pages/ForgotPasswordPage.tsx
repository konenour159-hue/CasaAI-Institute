import { useState, type FormEvent } from "react";
import { Link } from "../components/AppLink";
import { authService } from "../services/authService";
import { ApiError } from "../services/apiClient";
import { RevealSection } from "../components/RevealSection";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await authService.forgotPassword(email);
      // Réponse volontairement identique que l'email existe ou non côté
      // serveur — le message ci-dessous ne doit jamais dire "cet email
      // n'existe pas" (cf. AuthService.request_password_reset).
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Une erreur est survenue.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "40px auto" }}>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.6rem", marginBottom: 8 }}>Mot de passe oublié</h1>
        <p style={{ marginBottom: 32 }}>Recevez un lien pour choisir un nouveau mot de passe.</p>

        {submitted ? (
          <div className="card" style={{ padding: 28 }}>
            <p className="success-text" style={{ marginBottom: 12 }}>
              Si un compte existe avec cet email, un lien de réinitialisation vient d'être envoyé.
            </p>
            <p style={{ fontSize: "0.9rem" }}>Vérifiez votre boîte de réception, y compris les indésirables.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            {error && <p className="error-text">{error}</p>}

            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Envoi…" : "Envoyer le lien"}
            </button>
          </form>
        )}

        <p style={{ marginTop: 20, fontSize: "0.9rem" }}>
          <Link to="/login" style={{ color: "var(--color-accent-blue)" }}>
            Retour à la connexion
          </Link>
        </p>
      </RevealSection>
    </div>
  );
}
