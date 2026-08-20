import { api } from "./apiClient";
import type { PortfolioEvidence } from "../types/api";

export interface PortfolioEvidenceInput {
  title: string;
  context?: string;
  problem?: string;
  role?: string;
  deliverable?: string;
  result?: string;
  skill_ids?: string[];
}

export const portfolioService = {
  create: (data: PortfolioEvidenceInput) => api.post<PortfolioEvidence>("/api/portfolio/evidence", data, true),
  listMine: () => api.get<PortfolioEvidence[]>("/api/me/portfolio", true),
  get: (id: string) => api.get<PortfolioEvidence>(`/api/portfolio/evidence/${id}`, true),
};
