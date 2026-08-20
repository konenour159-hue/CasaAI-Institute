import { api } from "./apiClient";
import type {
  CertificationDetail,
  CertificationEligibility,
  CertificationListItem,
  CourseCertificate,
  CourseCertificateEligibility,
} from "../types/api";

export const certificationService = {
  list: () => api.get<CertificationListItem[]>("/api/certifications"),
  get: (id: string) => api.get<CertificationDetail>(`/api/certifications/${id}`),
  getMyEligibility: (id: string) =>
    api.get<CertificationEligibility>(`/api/me/certifications/${id}/eligibility`, true),

  getCourseCertificateEligibility: (courseId: string) =>
    api.get<CourseCertificateEligibility>(`/api/courses/${courseId}/certificate/eligibility`, true),
  issueCourseCertificate: (courseId: string) =>
    api.post<CourseCertificate>(`/api/courses/${courseId}/certificate`, undefined, true),
  listMyCourseCertificates: () => api.get<CourseCertificate[]>("/api/me/course-certificates", true),
};
