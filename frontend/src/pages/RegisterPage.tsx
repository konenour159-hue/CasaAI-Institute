import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Link } from "../components/AppLink";
import { useAuth } from "../stores/authStore";
import { ApiError } from "../services/apiClient";
import { RevealSection } from "../components/RevealSection";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register({ first_name: firstName, last_name: lastName, email, password });
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Cet email est déjà utilisé.");
      } else {
        setError(err instanceof ApiError ? err.detail : "Une erreur est survenue.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: "40px auto" }}>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.6rem", marginBottom: 8 }}>Créer un compte</h1>
        <p style={{ marginBottom: 32 }}>
          Découvrez, apprenez, expérimentez, certifiez — à votre rythme.
        </p>

        <form onSubmit={handleSubmit} className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", gap: 12 }}>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="firstName">Prénom</label>
              <input id="firstName" required value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="lastName">Nom</label>
              <input id="lastName" required value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </div>
          </div>
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
          <div className="field">
            <label htmlFor="password">Mot de passe</label>
            <input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <span style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>8 caractères minimum</span>
          </div>

          {error && <p className="error-text">{error}</p>}

          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? "Création…" : "Créer mon compte"}
          </button>
        </form>

        <p style={{ marginTop: 20, fontSize: "0.9rem" }}>
          Déjà inscrit ?{" "}
          <Link to="/login" style={{ color: "var(--color-accent-blue)" }}>
            Se connecter
          </Link>
        </p>
      </RevealSection>
    </div>
  );
}
