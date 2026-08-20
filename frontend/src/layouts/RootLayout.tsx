import type { ReactNode } from "react";
import { Nav } from "../components/Nav";

export function RootLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Nav />
      <main style={{ flex: 1, padding: "40px 0 80px" }}>
        <div className="container">{children}</div>
      </main>
    </div>
  );
}
