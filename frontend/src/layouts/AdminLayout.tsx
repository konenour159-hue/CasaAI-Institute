import type { ReactNode } from "react";
import { NavLink } from "../components/AppLink";
import { useAuth } from "../stores/authStore";

// Onglets filtrés par rôle : "Utilisateurs" est réservé à SUPER_ADMIN
// (gestion des comptes, hors périmètre "contenu" d'un ADMIN simple).
// "Cours" et "Importer un PDF" sont accessibles aux deux rôles admin.
const TABS = [
  { to: "/admin/users", label: "Utilisateurs", roles: ["SUPER_ADMIN"] as const },
  { to: "/admin/progress", label: "Progression", roles: ["SUPER_ADMIN"] as const },
  { to: "/admin/certifications", label: "Certifications", roles: ["SUPER_ADMIN"] as const },
  { to: "/admin/courses", label: "Cours", roles: ["ADMIN", "SUPER_ADMIN"] as const },
  { to: "/admin/import-pdf", label: "Importer un PDF", roles: ["ADMIN", "SUPER_ADMIN"] as const },
];

export function AdminLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const visibleTabs = TABS.filter((tab) => user && (tab.roles as readonly string[]).includes(user.role));

  return (
    <div>
      <h1 style={{ fontSize: "1.6rem", marginBottom: 4 }}>Administration</h1>
      <p style={{ marginBottom: 28 }}>
        {user?.role === "SUPER_ADMIN"
          ? "Gestion des utilisateurs et du contenu pédagogique."
          : "Gestion du contenu pédagogique."}
      </p>

      <nav style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--color-border)", marginBottom: 32 }}>
        {visibleTabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            style={({ isActive }) => ({
              padding: "10px 16px",
              fontSize: "0.9rem",
              borderBottom: isActive ? "2px solid var(--color-accent-gold)" : "2px solid transparent",
              color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
              fontWeight: isActive ? 600 : 400,
            })}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      {children}
    </div>
  );
}
