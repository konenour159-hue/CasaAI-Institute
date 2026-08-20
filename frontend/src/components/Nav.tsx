import { useNavigate } from "react-router-dom";
import { Link } from "./AppLink";
import { useAuth } from "../stores/authStore";

export function Nav() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <header
      style={{
        borderBottom: "1px solid var(--color-border)",
        background: "rgba(255, 255, 255, 0.85)",
        backdropFilter: "blur(8px)",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <div
        className="container"
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 64 }}
      >
        <Link to="/" style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.1rem" }}>
          CASA <span style={{ color: "var(--color-accent-gold)" }}>AI</span> Institute
        </Link>

        <nav style={{ display: "flex", alignItems: "center", gap: 24, fontSize: "0.9rem" }}>
          <Link to="/catalog" className="nav-link">
            Catalogue
          </Link>
          {isAuthenticated && (
            <>
              <Link to="/app/dashboard" className="nav-link">
                Mon espace
              </Link>
              <Link to="/app/quizzes" className="nav-link">
                Quiz
              </Link>
              <Link to="/app/portfolio" className="nav-link">
                Portfolio
              </Link>
              <Link to="/app/certifications" className="nav-link">
                Certifications
              </Link>
              {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && (
                <Link to="/admin/courses" className="nav-link-accent">
                  Cours
                </Link>
              )}
              {user?.role === "SUPER_ADMIN" && (
                <Link to="/admin/users" className="nav-link-accent">
                  Utilisateurs
                </Link>
              )}
            </>
          )}

          {isAuthenticated ? (
            <>
              <Link to="/app/profile" className="mono nav-link" style={{ fontSize: "0.8rem" }}>
                {user?.first_name}
              </Link>
              <button className="btn btn-secondary" onClick={handleLogout}>
                Se déconnecter
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link">
                Connexion
              </Link>
              <Link to="/register" className="btn btn-primary">
                S'inscrire
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
