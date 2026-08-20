import { Link } from "../components/AppLink";
import { RevealSection } from "../components/RevealSection";
import { HeroVisual } from "../components/HeroVisual";
import { ProgressRail } from "../components/ProgressRail";

export function HomePage() {
  return (
    <div>
      <section className="hero-grid">
        <div style={{ maxWidth: 560 }}>
          <RevealSection as="div" delayMs={0}>
            <span className="badge badge-gold" style={{ marginBottom: 20 }}>
              IA · DATA · MLOPS · GOUVERNANCE
            </span>
          </RevealSection>
          <RevealSection as="div" delayMs={80}>
            <h1 style={{ fontSize: "2.6rem", marginTop: 16, marginBottom: 20 }}>
              Une trajectoire complète, de la découverte à la certification.
            </h1>
          </RevealSection>
          <RevealSection as="div" delayMs={160}>
            <p style={{ fontSize: "1.05rem", marginBottom: 32 }}>
              CASA AI Institute structure l'apprentissage de l'intelligence
              artificielle en une seule logique, du premier cours au projet final
              évalué par les pairs.
            </p>
          </RevealSection>
          <RevealSection as="div" delayMs={240}>
            <div style={{ display: "flex", gap: 12 }}>
              <Link to="/register" className="btn btn-primary">
                Commencer gratuitement
              </Link>
              <Link to="/catalog" className="btn btn-secondary">
                Explorer le catalogue
              </Link>
            </div>
          </RevealSection>
        </div>

        <RevealSection as="div" delayMs={320} className="hero-visual">
          <HeroVisual />
        </RevealSection>
      </section>

      {/* Signature : la séquence pédagogique du cahier des charges, rendue
          comme un rail — c'est une vraie séquence fixe, pas un ornement.
          Léger relief (chemin qui ondule plutôt qu'une ligne plate) et
          étape courante mise en avant pour un apprenant connecté — cf.
          audit §4 point 5. Le <ol> porte la sémantique de séquence même si
          la présentation visuelle est absolument positionnée. */}
      <section aria-label="Notre méthode" style={{ marginBottom: 48 }}>
        <RevealSection as="div">
          <ProgressRail />
        </RevealSection>
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
        {[
          { title: "Parcours structurés", body: "Des trajectoires pensées par profil : Direction, Manager, Consultant, Data Engineer…" },
          { title: "Laboratoires pratiques", body: "Chaque compétence se démontre par un livrable réel, pas seulement un quiz." },
          { title: "Certifications", body: "Des critères explicites : cours, scores, compétences, preuves de portfolio." },
        ].map((item, i) => (
          <RevealSection key={item.title} as="div" delayMs={i * 80}>
            <div className="card" style={{ padding: 24, height: "100%" }}>
              <h3 style={{ fontSize: "1.05rem", marginBottom: 10 }}>{item.title}</h3>
              <p>{item.body}</p>
            </div>
          </RevealSection>
        ))}
      </section>
    </div>
  );
}
