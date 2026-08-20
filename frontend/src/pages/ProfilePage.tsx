import { useEffect, useState, type FormEvent } from "react";
import { Link } from "../components/AppLink";
import { useAuth } from "../stores/authStore";
import { authService } from "../services/authService";
import { progressService } from "../services/progressService";
import { certificationService } from "../services/certificationService";
import { portfolioService } from "../services/portfolioService";
import { profileService } from "../services/profileService";
import { contentService } from "../services/contentService";
import { ApiError } from "../services/apiClient";
import { RevealSection } from "../components/RevealSection";
import type {
  CourseCertificate,
  Goal,
  PortfolioEvidence,
  ProfileType,
  QuizAttemptHistoryItem,
  Skill,
  UserRole,
  UserSkillProgress,
} from "../types/api";

const ROLE_LABELS: Record<UserRole, string> = {
  LEARNER: "Apprenant",
  ADMIN: "Administrateur",
  SUPER_ADMIN: "Super administrateur",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function StatCard({ to, value, label }: { to: string; value: string; label: string }) {
  return (
    <Link to={to} className="card" style={{ padding: 20 }}>
      <p style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: "1.7rem", margin: "0 0 4px" }}>
        {value}
      </p>
      <p className="text-caption">{label}</p>
    </Link>
  );
}

export function ProfilePage() {
  const { user, updateUser } = useAuth();

  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [currentPasswordForEmail, setCurrentPasswordForEmail] = useState("");
  const [infoError, setInfoError] = useState<string | null>(null);
  const [infoSuccess, setInfoSuccess] = useState(false);
  const [savingInfo, setSavingInfo] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [savingPw, setSavingPw] = useState(false);

  const [skills, setSkills] = useState<UserSkillProgress[] | null>(null);
  const [certificates, setCertificates] = useState<CourseCertificate[] | null>(null);
  const [portfolioItems, setPortfolioItems] = useState<PortfolioEvidence[] | null>(null);
  const [quizHistory, setQuizHistory] = useState<QuizAttemptHistoryItem[] | null>(null);

  const [profileTypes, setProfileTypes] = useState<ProfileType[]>([]);
  const [goalsCatalog, setGoalsCatalog] = useState<Goal[]>([]);
  const [skillsCatalog, setSkillsCatalog] = useState<Skill[]>([]);
  const [profileTypeId, setProfileTypeId] = useState("");
  const [level, setLevel] = useState("");
  const [careerObjectives, setCareerObjectives] = useState("");
  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [learningError, setLearningError] = useState<string | null>(null);
  const [learningSuccess, setLearningSuccess] = useState(false);
  const [savingLearning, setSavingLearning] = useState(false);

  useEffect(() => {
    progressService.getMySkills().then(setSkills).catch(() => setSkills([]));
    certificationService.listMyCourseCertificates().then(setCertificates).catch(() => setCertificates([]));
    portfolioService.listMine().then(setPortfolioItems).catch(() => setPortfolioItems([]));
    progressService.getMyQuizHistory().then(setQuizHistory).catch(() => setQuizHistory([]));

    contentService.listProfileTypes().then(setProfileTypes).catch(() => setProfileTypes([]));
    contentService.listGoals().then(setGoalsCatalog).catch(() => setGoalsCatalog([]));
    contentService.listSkills().then(setSkillsCatalog).catch(() => setSkillsCatalog([]));
    profileService
      .getMyOnboardingProfile()
      .then((p) => {
        setProfileTypeId(p.profile_type_id ?? "");
        setLevel(p.level ?? "");
        setCareerObjectives(p.career_objectives ?? "");
        setSelectedGoals(p.goal_ids);
        setSelectedSkills(p.interest_skill_ids);
      })
      .catch(() => {});
  }, []);

  const toggleGoal = (id: string) => {
    setSelectedGoals((prev) => (prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]));
  };
  const toggleInterestSkill = (id: string) => {
    setSelectedSkills((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  };

  if (!user) return null;

  const emailChanged = email !== user.email;

  const handleInfoSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setInfoError(null);
    setInfoSuccess(false);
    setSavingInfo(true);
    try {
      const updated = await authService.updateMe({
        first_name: firstName,
        last_name: lastName,
        email,
        current_password: emailChanged ? currentPasswordForEmail : undefined,
      });
      updateUser(updated);
      setCurrentPasswordForEmail("");
      setInfoSuccess(true);
    } catch (err) {
      setInfoError(err instanceof ApiError ? err.detail : "Une erreur est survenue.");
    } finally {
      setSavingInfo(false);
    }
  };

  const handleLearningSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLearningError(null);
    setLearningSuccess(false);
    setSavingLearning(true);
    try {
      await profileService.updateMyOnboardingProfile({
        profile_type_id: profileTypeId || null,
        level: level || null,
        career_objectives: careerObjectives || null,
        goal_ids: selectedGoals,
        interest_skill_ids: selectedSkills,
      });
      setLearningSuccess(true);
    } catch (err) {
      setLearningError(err instanceof ApiError ? err.detail : "Une erreur est survenue.");
    } finally {
      setSavingLearning(false);
    }
  };

  const handlePasswordSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(false);
    if (newPassword !== confirmPassword) {
      setPwError("Les mots de passe ne correspondent pas.");
      return;
    }
    setSavingPw(true);
    try {
      await authService.changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPwSuccess(true);
    } catch (err) {
      setPwError(err instanceof ApiError ? err.detail : "Une erreur est survenue.");
    } finally {
      setSavingPw(false);
    }
  };

  const averageQuizScore =
    quizHistory && quizHistory.length > 0
      ? Math.round(quizHistory.reduce((sum, q) => sum + q.score, 0) / quizHistory.length)
      : null;
  const skillsInProgress = skills?.filter((s) => s.mastery_level > 0).length ?? null;

  return (
    <div style={{ maxWidth: 680 }}>
      <RevealSection as="div">
        <h1 style={{ fontSize: "1.8rem", marginBottom: 4 }}>Mon profil</h1>
        <p style={{ marginBottom: 20 }}>Gérez vos informations de compte et suivez votre parcours.</p>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 40, flexWrap: "wrap" }}>
          <span className="badge badge-gold">{ROLE_LABELS[user.role]}</span>
          <span className="mono" style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
            Membre depuis {formatDate(user.created_at)}
          </span>
          {user.last_login_at && (
            <span className="mono" style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
              Dernière connexion {formatDate(user.last_login_at)}
            </span>
          )}
        </div>
      </RevealSection>

      <RevealSection as="div" delayMs={80}>
        <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Informations du compte</h2>
        <form
          onSubmit={handleInfoSubmit}
          className="card"
          style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16, marginBottom: 40 }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label htmlFor="first_name">Prénom</label>
              <input
                id="first_name"
                required
                autoComplete="given-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="last_name">Nom</label>
              <input
                id="last_name"
                required
                autoComplete="family-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
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

          {emailChanged && (
            <div className="field">
              <label htmlFor="current_password_email">
                Mot de passe actuel (pour confirmer le changement d'email)
              </label>
              <input
                id="current_password_email"
                type="password"
                required
                autoComplete="current-password"
                value={currentPasswordForEmail}
                onChange={(e) => setCurrentPasswordForEmail(e.target.value)}
              />
            </div>
          )}

          {infoError && <p className="error-text">{infoError}</p>}
          {infoSuccess && <p className="success-text">Informations mises à jour.</p>}

          <button type="submit" className="btn btn-primary" disabled={savingInfo} style={{ alignSelf: "flex-start" }}>
            {savingInfo ? "Enregistrement…" : "Enregistrer"}
          </button>
        </form>
      </RevealSection>

      <RevealSection as="div" delayMs={120}>
        <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Profil d'apprentissage</h2>
        <form
          onSubmit={handleLearningSubmit}
          className="card"
          style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16, marginBottom: 40 }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label htmlFor="profile_type">Profil</label>
              <select
                id="profile_type"
                value={profileTypeId}
                onChange={(e) => setProfileTypeId(e.target.value)}
                style={{
                  background: "var(--color-surface-raised)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  padding: "10px 12px",
                }}
              >
                <option value="">Non renseigné</option>
                {profileTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="level">Niveau</label>
              <input
                id="level"
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                placeholder="ex : débutant, intermédiaire, avancé"
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="career_objectives">Objectifs de carrière</label>
            <textarea
              id="career_objectives"
              rows={3}
              value={careerObjectives}
              onChange={(e) => setCareerObjectives(e.target.value)}
              style={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: "10px 12px",
                fontFamily: "inherit",
                fontSize: "0.95rem",
                resize: "vertical",
              }}
            />
          </div>

          <div className="field">
            <label>Ce que vous cherchez à faire</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {goalsCatalog.map((g) => (
                <button
                  type="button"
                  key={g.id}
                  onClick={() => toggleGoal(g.id)}
                  className="badge"
                  style={{
                    cursor: "pointer",
                    border: "1px solid var(--color-border)",
                    background: selectedGoals.includes(g.id) ? "var(--color-accent-blue-soft)" : "transparent",
                    color: selectedGoals.includes(g.id) ? "var(--color-accent-blue)" : "var(--color-text-muted)",
                  }}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label>Compétences déjà acquises</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 140, overflowY: "auto", padding: 4 }}>
              {skillsCatalog.map((s) => (
                <button
                  type="button"
                  key={s.id}
                  onClick={() => toggleInterestSkill(s.id)}
                  className="badge"
                  style={{
                    cursor: "pointer",
                    border: "1px solid var(--color-border)",
                    background: selectedSkills.includes(s.id) ? "var(--color-accent-blue-soft)" : "transparent",
                    color: selectedSkills.includes(s.id) ? "var(--color-accent-blue)" : "var(--color-text-muted)",
                  }}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>

          {learningError && <p className="error-text">{learningError}</p>}
          {learningSuccess && <p className="success-text">Profil d'apprentissage mis à jour.</p>}

          <button type="submit" className="btn btn-primary" disabled={savingLearning} style={{ alignSelf: "flex-start" }}>
            {savingLearning ? "Enregistrement…" : "Enregistrer"}
          </button>
        </form>
      </RevealSection>

      <RevealSection as="div" delayMs={160}>
        <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Sécurité</h2>
        <form
          onSubmit={handlePasswordSubmit}
          className="card"
          style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16, marginBottom: 40 }}
        >
          <div className="field">
            <label htmlFor="current_password">Mot de passe actuel</label>
            <input
              id="current_password"
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </div>
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
            <label htmlFor="confirm_password">Confirmer le nouveau mot de passe</label>
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

          {pwError && <p className="error-text">{pwError}</p>}
          {pwSuccess && <p className="success-text">Mot de passe modifié.</p>}

          <button type="submit" className="btn btn-primary" disabled={savingPw} style={{ alignSelf: "flex-start" }}>
            {savingPw ? "Enregistrement…" : "Changer le mot de passe"}
          </button>
        </form>
      </RevealSection>

      <RevealSection as="div" delayMs={200}>
        <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Vue d'ensemble</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 16 }}>
          <StatCard
            to="/app/dashboard"
            value={skillsInProgress === null ? "…" : String(skillsInProgress)}
            label="Compétences en progrès"
          />
          <StatCard
            to="/app/certifications"
            value={certificates === null ? "…" : String(certificates.length)}
            label={`Certificat${(certificates?.length ?? 0) > 1 ? "s" : ""} obtenu${(certificates?.length ?? 0) > 1 ? "s" : ""}`}
          />
          <StatCard
            to="/app/portfolio"
            value={portfolioItems === null ? "…" : String(portfolioItems.length)}
            label="Évidences de portfolio"
          />
          <StatCard
            to="/app/quizzes"
            value={averageQuizScore === null ? "—" : `${averageQuizScore}/100`}
            label="Score moyen aux quiz"
          />
        </div>
      </RevealSection>
    </div>
  );
}
