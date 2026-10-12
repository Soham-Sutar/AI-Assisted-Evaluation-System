import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { BarChart3, BookOpen, ClipboardCheck, FileText, Gauge, GraduationCap, History, LogOut, ScanText, Settings, Shuffle, UserCog, Flag, ListChecks } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

const NAV = {
  ADMIN: [["/admin/dashboard", "Dashboard", Gauge], ["/admin/exams", "Exams", BookOpen], ["/admin/students", "Students", GraduationCap],
    ["/admin/faculty", "Faculty", UserCog], ["/admin/answersheets", "Answer sheets", FileText], ["/admin/segmentation", "Segmentation review", ScanText],
    ["/admin/assignments", "Assignments", Shuffle], ["/admin/evaluations", "Evaluations", ClipboardCheck], ["/admin/reviews", "Reviews", Flag],
    ["/admin/results", "Results", ListChecks], ["/admin/analytics", "Analytics", BarChart3], ["/admin/audit-logs", "Audit logs", History], ["/admin/settings", "Settings", Settings]],
  FACULTY: [["/faculty/dashboard", "Dashboard", Gauge], ["/faculty/assignments", "My assignments", ClipboardCheck]],
  REVIEWER: [["/reviewer/dashboard", "Dashboard", Gauge], ["/reviewer/reviews", "Review queue", Flag]],
} as const;

export function AppLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) return null;
  return <div className="flex min-h-screen">
    <aside className="hidden w-60 shrink-0 flex-col bg-slate-900 text-slate-200 md:flex">
      <div className="px-5 py-5"><p className="text-xl font-bold text-white">EvalAI</p><p className="text-xs text-slate-400">Modular Examination Evaluation</p></div>
      <nav className="flex-1 space-y-0.5 px-2" aria-label="Main">
        {NAV[user.role].map(([to, label, Icon]) => <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2 text-sm ${isActive ? "bg-brand-600 text-white" : "hover:bg-slate-800"}`}><Icon className="h-4 w-4" />{label}</NavLink>)}
      </nav>
      <div className="border-t border-slate-800 p-4 text-sm"><p className="truncate font-medium text-white">{user.full_name}</p><p className="text-xs text-slate-400">{user.role}</p>
        <button onClick={() => { logout(); nav("/login"); }} className="mt-3 flex items-center gap-2 text-slate-300 hover:text-white"><LogOut className="h-4 w-4" />Sign out</button></div>
    </aside>
    <main className="min-w-0 flex-1 p-4 md:p-8">
      <div className="mb-4 flex items-center justify-between md:hidden"><p className="font-bold">EvalAI</p><button onClick={() => { logout(); nav("/login"); }} className="text-sm text-slate-600">Sign out</button></div>
      <Outlet /></main></div>;
}
