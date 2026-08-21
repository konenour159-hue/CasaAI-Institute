import { api } from "./apiClient";
import type {
  LabResult,
  LessonDetail,
  LessonDocument,
  Quiz,
  QuizAttemptHistoryItem,
  QuizAttemptResult,
  QuizListItem,
  UserLessonProgress,
  UserSkillProgress,
} from "../types/api";

export const progressService = {
  getLesson: (id: string) => api.get<LessonDetail>(`/api/lessons/${id}`, true),
  getLessonDocument: (id: string) => api.get<LessonDocument>(`/api/lessons/${id}/document`, true),
  completeLesson: (id: string) =>
    api.post<{ lesson_id: string; status: string; progress_pct: number }>(
      `/api/lessons/${id}/complete`,
      undefined,
      true
    ),

  getMyProgress: () => api.get<UserLessonProgress[]>("/api/me/progress", true),
  getMySkills: () => api.get<UserSkillProgress[]>("/api/me/skills", true),

  listQuizzes: () => api.get<QuizListItem[]>("/api/quizzes", true),
  getQuiz: (id: string) => api.get<Quiz>(`/api/quizzes/${id}`, true),
  getQuizBySkill: (skillId: string) => api.get<Quiz>(`/api/skills/${skillId}/quiz`, true),
  attemptQuiz: (id: string, answers: { question_id: string; selected_option_id: string | null }[]) =>
    api.post<QuizAttemptResult>(`/api/quizzes/${id}/attempt`, { answers }, true),
  getMyQuizHistory: () => api.get<QuizAttemptHistoryItem[]>("/api/me/quiz-history", true),

  submitLab: (id: string, payload: { mode?: string; submission?: Record<string, unknown>; score?: number }) =>
    api.post<LabResult>(`/api/labs/${id}/submit`, payload, true),
  getMyLabResults: () => api.get<LabResult[]>("/api/me/lab-results", true),
};
