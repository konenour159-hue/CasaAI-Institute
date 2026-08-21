// Miroir des schémas Pydantic de app/schemas/*.py — garder synchronisé
// manuellement tant qu'il n'y a pas de génération automatique depuis l'OpenAPI.

import type { MiniDiagramData } from "../components/MiniDiagram";

// ADMIN : gestion de contenu (cours/leçons/import PDF) uniquement.
// SUPER_ADMIN : sur-ensemble d'ADMIN + utilisateurs, progression globale,
// certifications. Ne participe pas aux cours en tant qu'apprenant.
export type UserRole = "ADMIN" | "SUPER_ADMIN" | "LEARNER";
export type AccountStatus = "ACTIVE" | "SUSPENDED" | "PENDING";
export type LessonProgressStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";
export type ContentStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";

// --- Auth -----------------------------------------------------------

export interface UserPublic {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// --- Contenu (public) -----------------------------------------------------

export interface School {
  id: string;
  name: string;
  short_name: string;
  color: string;
  description: string | null;
}

export interface Skill {
  id: string;
  school_id: string;
  name: string;
  description: string | null;
}

export interface ProfileType {
  id: string;
  name: string;
  description: string | null;
}

export interface Goal {
  id: string;
  label: string;
}

export interface UserProfile {
  profile_type_id: string | null;
  level: string | null;
  career_objectives: string | null;
  onboarding_done: boolean;
  goal_ids: string[];
  interest_skill_ids: string[];
}

export interface LessonSummary {
  id: string;
  title: string;
  level: string | null;
  duration_min: number | null;
  position: number;
}

export interface CourseListItem {
  id: string;
  school_id: string;
  title: string;
  level: string | null;
  duration_min: number | null;
  color: string | null;
  description: string | null;
}

export interface CourseResource {
  id: string;
  title: string;
  type: string | null;
  url: string | null;
  publisher: string | null;
  year: number | null;
  description: string | null;
}

export interface CourseDetail extends CourseListItem {
  lessons: LessonSummary[];
  final_quiz_id: string | null;
  resources: CourseResource[];
}

export interface PathwayListItem {
  id: string;
  title: string;
  profile_label: string | null;
  level: string | null;
  duration_label: string | null;
  color: string | null;
  description: string | null;
}

export interface PathwayDetail extends PathwayListItem {
  courses: CourseListItem[];
}

export interface LabListItem {
  id: string;
  title: string;
  school_id: string | null;
  level: string | null;
  duration_min: number | null;
  color: string | null;
  description: string | null;
}

export interface LabInteractiveStep {
  key: string;
  title: string;
  summary: string;
  detail: string;
  highlights: string[];
}

export interface LabDetail extends LabListItem {
  environment: string | null;
  instructions: string | null;
  dataset_ref: string | null;
  deliverable: string | null;
  evaluation_note: string | null;
  modes: string[];
  skills: string[];
  interactive_steps: LabInteractiveStep[] | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Progression (authentifié) -----------------------------------------

export interface LessonSection {
  position: number;
  title: string;
  body: string;
  image_url?: string | null;
  image_alt?: string | null;
  diagram?: MiniDiagramData | null;
}

export interface LessonDepthLevel {
  depth_key: "ESSENTIAL" | "TECHNICAL" | "MATHEMATICS" | "IMPLEMENTATION" | "ARCHITECTURE" | "GOVERNANCE";
  label: string;
  title: string;
  body: string;
}

export interface LessonDetail {
  id: string;
  course_id: string;
  title: string;
  level: string | null;
  duration_min: number | null;
  summary: string | null;
  example: string | null;
  position: number;
  skill_id: string | null;
  demo_id: string | null;
  objectives: string[];
  sections: LessonSection[];
  depth_levels: LessonDepthLevel[];
  validation_quiz_id: string | null;
}

export interface UserLessonProgress {
  lesson_id: string;
  lesson_title: string;
  course_id: string;
  status: LessonProgressStatus;
  progress_pct: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface UserSkillProgress {
  skill_id: string;
  skill_name: string;
  school_id: string;
  mastery_level: number;
  updated_at: string;
}

export interface QuizOption {
  id: string;
  position: number;
  option_text: string;
}

export interface QuizQuestion {
  id: string;
  question_text: string;
  options: QuizOption[];
}

export interface Quiz {
  id: string;
  title: string;
  kind: "PRACTICE" | "VALIDATION" | "FINAL";
  pass_threshold: number;
  questions: QuizQuestion[];
}

export interface QuizListItem {
  id: string;
  title: string;
  kind: "PRACTICE" | "VALIDATION" | "FINAL";
  course_id: string | null;
  lesson_id: string | null;
  skill_id: string | null;
  pass_threshold: number;
}

export interface QuizAnswerResult {
  question_id: string;
  selected_option_id: string | null;
  is_correct: boolean;
  correct_option_id: string;
  explanation: string | null;
}

export interface QuizAttemptResult {
  attempt_id: string;
  score: number;
  passed: boolean;
  correct_count: number;
  total_questions: number;
  answers: QuizAnswerResult[];
}

export interface QuizAttemptHistoryItem {
  attempt_id: string;
  quiz_id: string;
  quiz_title: string;
  score: number;
  passed: boolean;
  started_at: string;
  completed_at: string | null;
}

export interface LabResult {
  id: string;
  lab_id: string;
  mode: string | null;
  completed: boolean;
  score: number | null;
  feedback: string | null;
  submitted_at: string | null;
}

// --- Portfolio -----------------------------------------------------------

export interface PortfolioEvidence {
  id: string;
  title: string;
  context: string | null;
  problem: string | null;
  role: string | null;
  deliverable: string | null;
  result: string | null;
  metrics: Record<string, unknown> | null;
  feedback: string | null;
  skill_ids: string[];
  created_at: string;
  updated_at: string;
}

// --- Certifications -----------------------------------------------------

export interface CertificationListItem {
  id: string;
  title: string;
  level: string | null;
  description: string | null;
  color: string | null;
}

export interface CertificationRequirement {
  id: string;
  requirement_type: "COURSE" | "MIN_SCORE" | "LAB" | "SKILL" | "EVIDENCE" | "FINAL_PROJECT";
  description: string | null;
  course_id: string | null;
  lab_id: string | null;
  skill_id: string | null;
  min_score: number | null;
}

export interface CertificationDetail extends CertificationListItem {
  requirements: CertificationRequirement[];
}

export interface RequirementEligibility {
  requirement_id: string;
  requirement_type: string;
  description: string | null;
  satisfied: boolean | null;
  detail: string;
}

export interface CertificationEligibility {
  certification_id: string;
  eligible: boolean;
  requirements: RequirementEligibility[];
}

// --- Certificat de module (par cours, basé sur les quiz) ------------------

export interface CourseQuizScore {
  quiz_id: string;
  quiz_title: string;
  kind: string;
  best_score: number | null;
  attempted: boolean;
}

export interface CourseCertificateEligibility {
  course_id: string;
  threshold: number;
  quizzes: CourseQuizScore[];
  all_attempted: boolean;
  average_score: number | null;
  eligible: boolean;
  already_issued: boolean;
  issued_at: string | null;
}

export interface CourseCertificate {
  id: string;
  course_id: string;
  average_score: number;
  issued_at: string;
}

// --- Administration -----------------------------------------------------

export interface AdminUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  created_at: string;
  last_login_at: string | null;
}

export interface AdminLearnerProgressSummary {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  status: AccountStatus;
  lessons_completed: number;
  lessons_total_published: number;
  quizzes_attempted: number;
  quizzes_passed: number;
  quiz_average_score: number | null;
  labs_completed: number;
  last_activity_at: string | null;
}

export interface AdminLearnerLessonProgress {
  lesson_id: string;
  lesson_title: string;
  course_id: string;
  status: LessonProgressStatus;
  progress_pct: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface AdminLearnerQuizAttempt {
  attempt_id: string;
  quiz_id: string;
  quiz_title: string;
  score: number;
  passed: boolean;
  started_at: string;
  completed_at: string | null;
}

export interface AdminLearnerLabResult {
  result_id: string;
  lab_id: string;
  lab_title: string;
  mode: string | null;
  completed: boolean;
  score: number | null;
  submitted_at: string | null;
}

export interface AdminLearnerProgressDetail {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  status: AccountStatus;
  lessons: AdminLearnerLessonProgress[];
  quiz_attempts: AdminLearnerQuizAttempt[];
  lab_results: AdminLearnerLabResult[];
}

export interface AdminCourse {
  id: string;
  school_id: string;
  title: string;
  level: string | null;
  duration_min: number | null;
  color: string | null;
  description: string | null;
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED";
  created_at: string;
  updated_at: string;
}

export interface AdminLessonListItem {
  id: string;
  course_id: string;
  title: string;
  level: string | null;
  position: number;
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED";
}

export interface AdminLessonSectionInput {
  title: string;
  body: string;
  image_url?: string | null;
  image_alt?: string | null;
}

export interface AdminLessonDepthLevelInput {
  depth_key: "ESSENTIAL" | "TECHNICAL" | "MATHEMATICS" | "IMPLEMENTATION" | "ARCHITECTURE" | "GOVERNANCE";
  label: string;
  title: string;
  body: string;
}

export interface AdminLesson {
  id: string;
  course_id: string;
  skill_id: string | null;
  demo_id: string | null;
  title: string;
  level: string | null;
  duration_min: number | null;
  summary: string | null;
  example: string | null;
  position: number;
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED";
  objectives: string[];
  sections: AdminLessonSectionInput[];
  depth_levels: AdminLessonDepthLevelInput[];
}

export type QuizKind = "PRACTICE" | "VALIDATION" | "FINAL";

export interface AdminQuestionOptionInput {
  option_text: string;
  is_correct: boolean;
}

export interface AdminQuestionInput {
  question_text: string;
  explanation?: string | null;
  difficulty: number;
  options: AdminQuestionOptionInput[];
}

export interface AdminQuizInput {
  title: string;
  kind: QuizKind;
  lesson_id?: string | null;
  course_id?: string | null;
  skill_id?: string | null;
  pass_threshold: number;
  status: ContentStatus;
  questions: AdminQuestionInput[];
}

export interface AdminQuestionOption {
  id: string;
  option_text: string;
  is_correct: boolean;
}

export interface AdminQuestion {
  id: string;
  question_text: string;
  explanation: string | null;
  difficulty: number;
  options: AdminQuestionOption[];
}

export interface AdminQuiz {
  id: string;
  title: string;
  kind: QuizKind;
  lesson_id: string | null;
  course_id: string | null;
  skill_id: string | null;
  pass_threshold: number;
  status: ContentStatus;
  questions: AdminQuestion[];
}

export interface AdminQuizListItem {
  id: string;
  title: string;
  kind: QuizKind;
  lesson_id: string | null;
  course_id: string | null;
  skill_id: string | null;
  status: ContentStatus;
  question_count: number;
}

export interface AdminQuizListResponse {
  items: AdminQuizListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PdfImportResult {
  course_id: string;
  lesson_id: string;
  title: string;
  pages_extracted: number;
  warning: string | null;
  report: PdfQualityReport | null;
}

/** Rapport de qualité du moteur d'import (§28 du cahier import PDF). */
export interface PdfQualityReport {
  pages: number;
  sections: number;
  subsections: number;
  headings: number;
  paragraphs: number;
  blocks: number;
  lists: number;
  code_blocks: number;
  tables: number;
  formulas: number;
  captions: number;
  boilerplate_removed: number;
  multi_column_pages: number;
  average_confidence: number;
  document_type: string;
  text_extraction_confidence: number;
  anomalies: PdfImportAnomaly[];
}

export interface PdfImportAnomaly {
  kind: string;
  message: string;
  page: number | null;
  confidence: number | null;
}

export interface PdfPreviewBlock {
  kind: string;
  confidence: number;
  preview: string;
  items: string[] | { headers: string[] | null; rows: string[][] } | null;
}

export interface PdfPreviewSection {
  title: string;
  level: number;
  confidence: number;
  page_start: number | null;
  page_end: number | null;
  blocks: PdfPreviewBlock[];
  children: PdfPreviewSection[];
}

/** Ce que l'import produirait, rendu sans rien enregistrer (§29). */
export interface PdfPreviewResult {
  title: string;
  pages: number;
  report: PdfQualityReport;
  sections: PdfPreviewSection[];
}

// --- Certifications (SUPER_ADMIN) -------------------------------------------

export type AdminCertificationRequirementType = "COURSE" | "MIN_SCORE" | "LAB" | "SKILL" | "EVIDENCE" | "FINAL_PROJECT";

export interface AdminCertificationRequirementInput {
  requirement_type: AdminCertificationRequirementType;
  description?: string | null;
  course_id?: string | null;
  lab_id?: string | null;
  skill_id?: string | null;
  min_score?: number | null;
}

export interface AdminCertificationRequirement {
  id: string;
  requirement_type: AdminCertificationRequirementType;
  description: string | null;
  course_id: string | null;
  lab_id: string | null;
  skill_id: string | null;
  min_score: number | null;
  position: number;
}

export interface AdminCertificationListItem {
  id: string;
  title: string;
  level: string | null;
  status: ContentStatus;
  requirement_count: number;
  linked_requirement_count: number;
}

export interface AdminCertificationListResponse {
  items: AdminCertificationListItem[];
}

export interface AdminCertification {
  id: string;
  title: string;
  level: string | null;
  description: string | null;
  status: ContentStatus;
  requirements: AdminCertificationRequirement[];
}

export interface MediaUploadResult {
  url: string;
  content_type: string;
  size_bytes: number;
}
