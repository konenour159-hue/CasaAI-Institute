import { useEffect, useState } from "react";
import { AdminLayout } from "../../layouts/AdminLayout";
import { RevealSection } from "../../components/RevealSection";
import { ListSkeleton } from "../../components/Skeleton";
import { adminService } from "../../services/adminService";
import { useAuth } from "../../stores/authStore";
import type { AdminUser, UserRole } from "../../types/api";

const ROLE_LABELS: Record<UserRole, string> = {
  SUPER_ADMIN: "Super admin",
  ADMIN: "Admin (contenu)",
  LEARNER: "Apprenant",
};

const ROLE_BADGE_CLASS: Record<UserRole, string> = {
  SUPER_ADMIN: "badge-gold",
  ADMIN: "badge-teal",
  LEARNER: "badge-teal",
};

export function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    adminService.listUsers({ search: search || undefined, limit: 50 }).then((page) => {
      setUsers(page.items);
      setTotal(page.total);
    });
  };

  useEffect(refresh, [search]);

  const handleRoleChange = async (u: AdminUser, role: UserRole) => {
    if (role === u.role) return;
    setError(null);
    try {
      await adminService.updateUser(u.id, { role });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  };

  const handleStatusToggle = async (u: AdminUser) => {
    setError(null);
    try {
      await adminService.updateUser(u.id, { status: u.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE" });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  };

  const handleDelete = async (u: AdminUser) => {
    if (!confirm(`Supprimer définitivement le compte de ${u.first_name} ${u.last_name} ?`)) return;
    setError(null);
    try {
      await adminService.deleteUser(u.id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  };

  return (
    <AdminLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <input
          placeholder="Rechercher par nom ou email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 12px",
            fontSize: "0.9rem",
            width: 280,
          }}
        />
        <span className="mono" style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          {total} utilisateur{total > 1 ? "s" : ""}
        </span>
      </div>

      {error && <p className="error-text" style={{ marginBottom: 16 }}>{error}</p>}

      {users === null ? (
        <ListSkeleton count={5} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {users.map((u, i) => (
            <RevealSection key={u.id} as="div" delayMs={Math.min(i, 8) * 40}>
              <div className="card" style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ flex: 1 }}>
                  <p style={{ color: "var(--color-text)", fontWeight: 500 }}>
                    {u.first_name} {u.last_name}{" "}
                    {u.id === currentUser?.id && <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>(vous)</span>}
                  </p>
                  <p style={{ fontSize: "0.82rem" }}>{u.email}</p>
                </div>

                <span className={`badge ${ROLE_BADGE_CLASS[u.role]}`}>{ROLE_LABELS[u.role]}</span>
                <span
                  className="badge"
                  style={{
                    background: u.status === "ACTIVE" ? "var(--color-accent-teal-soft)" : "var(--color-accent-coral-soft)",
                    color: u.status === "ACTIVE" ? "var(--color-accent-teal)" : "var(--color-accent-coral)",
                  }}
                >
                  {u.status}
                </span>

                <select
                  value={u.role}
                  onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
                  disabled={u.id === currentUser?.id}
                  title={u.id === currentUser?.id ? "Vous ne pouvez pas changer votre propre rôle." : "Changer le rôle"}
                  style={{
                    background: "var(--color-surface-raised)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-sm)",
                    padding: "6px 10px",
                    fontSize: "0.85rem",
                  }}
                >
                  <option value="LEARNER">{ROLE_LABELS.LEARNER}</option>
                  <option value="ADMIN">{ROLE_LABELS.ADMIN}</option>
                  <option value="SUPER_ADMIN">{ROLE_LABELS.SUPER_ADMIN}</option>
                </select>
                <button className="btn btn-secondary" onClick={() => handleStatusToggle(u)} disabled={u.id === currentUser?.id}>
                  {u.status === "ACTIVE" ? "Suspendre" : "Réactiver"}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDelete(u)}
                  disabled={u.id === currentUser?.id}
                  style={{ color: "var(--color-accent-coral)" }}
                >
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
