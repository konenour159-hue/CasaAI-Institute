import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./stores/authStore";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RootLayout } from "./layouts/RootLayout";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { CatalogPage } from "./pages/CatalogPage";
import { CourseDetailPage } from "./pages/CourseDetailPage";
import { PathwayDetailPage } from "./pages/PathwayDetailPage";
import { LabDetailPage } from "./pages/LabDetailPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProfilePage } from "./pages/ProfilePage";
import { LessonPage } from "./pages/LessonPage";
import { QuizzesPage } from "./pages/QuizzesPage";
import { QuizTakePage } from "./pages/QuizTakePage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { CertificationsPage } from "./pages/CertificationsPage";
import { CertificationDetailPage } from "./pages/CertificationDetailPage";
import { RequireRole } from "./components/RequireRole";
import { AdminUsersPage } from "./pages/admin/AdminUsersPage";
import { AdminCoursesPage } from "./pages/admin/AdminCoursesPage";
import { AdminCourseLessonsPage } from "./pages/admin/AdminCourseLessonsPage";
import { AdminLessonEditPage } from "./pages/admin/AdminLessonEditPage";
import { AdminQuizEditPage } from "./pages/admin/AdminQuizEditPage";
import { AdminImportPdfPage } from "./pages/admin/AdminImportPdfPage";
import { AdminProgressPage } from "./pages/admin/AdminProgressPage";
import { AdminLearnerProgressDetailPage } from "./pages/admin/AdminLearnerProgressDetailPage";
import { AdminCertificationsPage } from "./pages/admin/AdminCertificationsPage";
import { AdminCertificationEditPage } from "./pages/admin/AdminCertificationEditPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RootLayout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/catalog" element={<CatalogPage />} />
            <Route path="/pathways/:pathwayId" element={<PathwayDetailPage />} />
            <Route path="/courses/:courseId" element={<CourseDetailPage />} />
            <Route path="/labs/:labId" element={<LabDetailPage />} />

            <Route
              path="/app/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/lessons/:lessonId"
              element={
                <ProtectedRoute>
                  <LessonPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/skills/:skillId/practice"
              element={
                <ProtectedRoute>
                  <QuizTakePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/quizzes"
              element={
                <ProtectedRoute>
                  <QuizzesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/quizzes/:quizId"
              element={
                <ProtectedRoute>
                  <QuizTakePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/portfolio"
              element={
                <ProtectedRoute>
                  <PortfolioPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/certifications"
              element={
                <ProtectedRoute>
                  <CertificationsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app/certifications/:certificationId"
              element={
                <ProtectedRoute>
                  <CertificationDetailPage />
                </ProtectedRoute>
              }
            />

            {/* Réservé à SUPER_ADMIN : gestion des utilisateurs (§ hors périmètre ADMIN contenu) */}
            <Route
              path="/admin/users"
              element={
                <RequireRole roles={["SUPER_ADMIN"]}>
                  <AdminUsersPage />
                </RequireRole>
              }
            />

            {/* Réservé à SUPER_ADMIN : progression globale des apprenants */}
            <Route
              path="/admin/progress"
              element={
                <RequireRole roles={["SUPER_ADMIN"]}>
                  <AdminProgressPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/progress/:userId"
              element={
                <RequireRole roles={["SUPER_ADMIN"]}>
                  <AdminLearnerProgressDetailPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/certifications"
              element={
                <RequireRole roles={["SUPER_ADMIN"]}>
                  <AdminCertificationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/certifications/:certificationId"
              element={
                <RequireRole roles={["SUPER_ADMIN"]}>
                  <AdminCertificationEditPage />
                </RequireRole>
              }
            />

            {/* Ouvert à ADMIN et SUPER_ADMIN : gestion de contenu pédagogique */}
            <Route
              path="/admin/courses"
              element={
                <RequireRole roles={["ADMIN", "SUPER_ADMIN"]}>
                  <AdminCoursesPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/courses/:courseId"
              element={
                <RequireRole roles={["ADMIN", "SUPER_ADMIN"]}>
                  <AdminCourseLessonsPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/courses/:courseId/lessons/:lessonId"
              element={
                <RequireRole roles={["ADMIN", "SUPER_ADMIN"]}>
                  <AdminLessonEditPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/quizzes/:quizId"
              element={
                <RequireRole roles={["ADMIN", "SUPER_ADMIN"]}>
                  <AdminQuizEditPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/import-pdf"
              element={
                <RequireRole roles={["ADMIN", "SUPER_ADMIN"]}>
                  <AdminImportPdfPage />
                </RequireRole>
              }
            />
          </Routes>
        </RootLayout>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
