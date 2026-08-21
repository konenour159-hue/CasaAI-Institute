import type { DocumentBlock, DocumentSection } from "../types/api";

/**
 * Rendu de la structure documentaire d'une leçon importée.
 *
 * Ce que l'affichage plat perdait : le corps d'une section y est une chaîne
 * rendue dans un seul `<p>`, où une liste redevient du texte courant, un
 * extrait de code perd sa chasse fixe et un tableau ses colonnes. Le moteur
 * d'import a pourtant reconnu chacun d'eux ; il suffit de les rendre.
 *
 * Les leçons écrites à la main ne passent jamais par ici — elles n'ont pas de
 * document, et gardent leur affichage d'origine.
 */

function isTable(
  items: DocumentBlock["items"],
): items is { headers: string[] | null; rows: string[][] } {
  return items !== null && !Array.isArray(items);
}

function Block({ block }: { block: DocumentBlock }) {
  if (block.kind === "LIST" && Array.isArray(block.items) && block.items.length > 0) {
    return (
      <ul className="lesson-block-list">
        {block.items.map((item, index) => (
          <li key={index}>{item.replace(/^\s*[-–—•·*▪◦‣]\s*/, "")}</li>
        ))}
      </ul>
    );
  }

  if (block.kind === "CODE") {
    return (
      <pre className="lesson-block-code">
        <code>{block.text}</code>
      </pre>
    );
  }

  if (block.kind === "TABLE" && isTable(block.items)) {
    const { headers, rows } = block.items;
    return (
      <div className="lesson-block-table-wrap">
        <table className="lesson-block-table">
          {headers && (
            <thead>
              <tr>{headers.map((cell, index) => <th key={index}>{cell}</th>)}</tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((cell, index) => <td key={index}>{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (block.kind === "FORMULA") {
    return <p className="lesson-block-formula">{block.text}</p>;
  }

  if (block.kind === "CAPTION") {
    return <p className="lesson-block-caption">{block.text}</p>;
  }

  return <p className="lesson-section-body">{block.text}</p>;
}

function Section({ section, depth }: { section: DocumentSection; depth: number }) {
  // Le niveau documentaire (1 à 4) devient un niveau de titre HTML décalé
  // d'un cran : le titre de la leçon occupe déjà le h1 de la page.
  const Heading = (["h2", "h3", "h4", "h5"][Math.min(depth, 3)] ?? "h5") as "h2";

  return (
    <section style={{ marginBottom: depth === 0 ? 28 : 18 }}>
      <Heading className={depth === 0 ? "lesson-section-title" : "lesson-subsection-title"}>
        {section.title}
        {section.confidence < 0.6 && (
          <span className="lesson-uncertain" title="Titre reconnu avec peu de certitude">
            à vérifier
          </span>
        )}
      </Heading>
      {section.blocks.map((block, index) => <Block key={index} block={block} />)}
      {section.children.map((child, index) => (
        <Section key={`${child.title}-${index}`} section={child} depth={depth + 1} />
      ))}
    </section>
  );
}

export function LessonDocumentView({
  sections,
  sourceFile,
}: {
  sections: DocumentSection[];
  sourceFile: string;
}) {
  return (
    <div className="card" style={{ padding: 28, marginBottom: 24 }}>
      <p className="lesson-document-source">
        Reconstruit depuis <strong>{sourceFile}</strong>
      </p>
      {sections.map((section, index) => (
        <Section key={`${section.title}-${index}`} section={section} depth={0} />
      ))}
    </div>
  );
}
