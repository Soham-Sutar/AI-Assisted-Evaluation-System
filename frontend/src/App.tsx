import { Navigate, Route, Routes } from "react-router-dom";
import { homeFor, useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import Login from "./pages/Login";
import { AdminDashboard, ExamDetail, Exams, FacultyAdmin, Students } from "./pages/admin/Core";
import { AnswerSheets, Assignments, Segmentation } from "./pages/admin/Pipeline";
import { Analytics, AuditLogs, Evaluations, Results, SettingsPage } from "./pages/admin/Reports";
import { FacultyAssignments, FacultyDashboard, FacultyEvaluate } from "./pages/faculty/Faculty";
import { ReviewDetail, ReviewQueue, ReviewerDashboard } from "./pages/reviewer/Reviewer";

export default function App() {
  const { user, loading } = useAuth();
  return <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/" element={loading ? null : <Navigate to={user ? homeFor(user.role) : "/login"} replace />} />
    <Route element={<ProtectedRoute roles={["ADMIN"]} />}><Route element={<AppLayout />}>
      <Route path="/admin/dashboard" element={<AdminDashboard />} /><Route path="/admin/exams" element={<Exams />} />
      <Route path="/admin/exams/:id" element={<ExamDetail />} /><Route path="/admin/exams/:id/questions" element={<ExamDetail />} />
      <Route path="/admin/students" element={<Students />} /><Route path="/admin/faculty" element={<FacultyAdmin />} />
      <Route path="/admin/answersheets" element={<AnswerSheets />} /><Route path="/admin/segmentation" element={<Segmentation />} />
      <Route path="/admin/assignments" element={<Assignments />} /><Route path="/admin/evaluations" element={<Evaluations />} />
      <Route path="/admin/reviews" element={<ReviewQueue base="/admin" />} /><Route path="/admin/review/:reviewId" element={<ReviewDetail base="/admin" />} />
      <Route path="/admin/results" element={<Results />} /><Route path="/admin/analytics" element={<Analytics />} />
      <Route path="/admin/audit-logs" element={<AuditLogs />} /><Route path="/admin/settings" element={<SettingsPage />} /></Route></Route>
    <Route element={<ProtectedRoute roles={["FACULTY"]} />}><Route element={<AppLayout />}>
      <Route path="/faculty/dashboard" element={<FacultyDashboard />} /><Route path="/faculty/assignments" element={<FacultyAssignments />} />
      <Route path="/faculty/evaluate/:answerId" element={<FacultyEvaluate />} /></Route></Route>
    <Route element={<ProtectedRoute roles={["REVIEWER"]} />}><Route element={<AppLayout />}>
      <Route path="/reviewer/dashboard" element={<ReviewerDashboard />} /><Route path="/reviewer/reviews" element={<ReviewQueue base="/reviewer" />} />
      <Route path="/reviewer/review/:reviewId" element={<ReviewDetail base="/reviewer" />} /></Route></Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}
