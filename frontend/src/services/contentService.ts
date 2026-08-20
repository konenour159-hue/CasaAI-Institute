import { api } from "./apiClient";
import type {
  CourseDetail,
  CourseListItem,
  LabDetail,
  LabListItem,
  Page,
  PathwayDetail,
  PathwayListItem,
  School,
  Skill,
} from "../types/api";

export const contentService = {
  listSchools: () => api.get<School[]>("/api/schools"),
  listSkills: (schoolId?: string) =>
    api.get<Skill[]>(`/api/skills${schoolId ? `?school_id=${schoolId}` : ""}`),

  listCourses: (params: { schoolId?: string; level?: string; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.schoolId) q.set("school_id", params.schoolId);
    if (params.level) q.set("level", params.level);
    q.set("limit", String(params.limit ?? 20));
    q.set("offset", String(params.offset ?? 0));
    return api.get<Page<CourseListItem>>(`/api/courses?${q.toString()}`);
  },
  getCourse: (id: string) => api.get<CourseDetail>(`/api/courses/${id}`),

  listPathways: (params: { level?: string; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.level) q.set("level", params.level);
    q.set("limit", String(params.limit ?? 20));
    q.set("offset", String(params.offset ?? 0));
    return api.get<Page<PathwayListItem>>(`/api/pathways?${q.toString()}`);
  },
  getPathway: (id: string) => api.get<PathwayDetail>(`/api/pathways/${id}`),

  listLabs: (params: { limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 20));
    q.set("offset", String(params.offset ?? 0));
    return api.get<Page<LabListItem>>(`/api/labs?${q.toString()}`);
  },
  getLab: (id: string) => api.get<LabDetail>(`/api/labs/${id}`),
};
