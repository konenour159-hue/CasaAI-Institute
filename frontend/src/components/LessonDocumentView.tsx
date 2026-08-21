import type { DocumentBlock, DocumentSection } from "../types/api";

/**
 * Rendu du document d'origine d'une leçon importée.
 *
 * Le PDF reconstruit, tel qu'il était à l'import : une liste y reste une
 * liste, un extrait de code garde sa chasse fixe, un tableau ses colonnes.
 *
 * Ce n'est **pas** la leçon. La leçon est le travail éditorial que l'admin
 * publie, et c'est elle que l'apprenant lit ; ce document en est la source,
 * figée, consultable à côté. Les avoir confondus faisait disparaître de la
 * page publiée les sections qu'un admin venait de retoucher.
 *
 * Pas de marqueur d'incertitude ici non plus : « à vérifier » s'adresse à qui
 * relit un import, pas à qui apprend. Il vit sur l'écran de prévisualisation.
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
      </Heading>
      {section.blocks.map((block, index) => <Block key={index} block={block} />)}
      {section.children.map((child, index) => (
        <Section key={`${child.title}-${index}`} section={child} depth={depth + 1} />
      ))}
    </section>
  );
}

export function LessonDocumentView({ sections }: { sections: DocumentSection[] }) {
  return (
    <div className="card" style={{ padding: 28, marginBottom: 24 }}>
      <p className="lesson-document-source">
        Reconstruit à l'import, avant toute retouche éditoriale.
      </p>
      {sections.map((section, index) => (
        <Section key={`${section.title}-${index}`} section={section} depth={0} />
      ))}
    </div>
  );
}
