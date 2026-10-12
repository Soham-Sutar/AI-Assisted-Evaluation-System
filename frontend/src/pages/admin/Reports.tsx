import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, downloadFile } from "../../lib/api";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, PageTitle, Select, Spinner, Stat, Table, Td } from "../../components/ui";
import { ExamPicker } from "./shared";

export function Evaluations() {
  const [examId, setExamId] = useState("");
  const q = useQuery({ queryKey: ["eval-history", examId], queryFn: () => api<any[]>(`/api/evaluations/history${examId ? `?exam_id=${examId}` : ""}`) });
  return <div><PageTitle title="Evaluation history" sub="Every submitted faculty evaluation, with the independent AI reference alongside." />
    <Card actions={<div className="w-64"><ExamPicker value={examId} onChange={setExamId} /></div>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title="No submitted evaluations yet" /> :
        <Table head={["Submitted", "Student", "Q", "Faculty", "Marks", "AI reference", "Comments"]}>{q.data.map((e) => <tr key={e.id}>
          <Td>{e.submitted_at && new Date(e.submitted_at).toLocaleString()}</Td><Td>{e.register_number}</Td><Td>Q{e.question_number}</Td><Td>{e.faculty_name}</Td><Td>{e.marks_awarded}/{e.max_marks}</Td>
          <Td>{e.ai_status === "COMPLETED" ? e.ai_marks : e.ai_status ? <Badge tone="yellow">{e.ai_status}</Badge> : "pending"}</Td><Td className="max-w-xs truncate text-xs">{e.comments}</Td></tr>)}</Table>}</Card></div>;
}

export function Results() {
  const qc = useQueryClient();
  const [examId, setExamId] = useState("");
  const q = useQuery({ queryKey: ["results", examId], queryFn: () => api<any>(`/api/exams/${examId}/results`), enabled: !!examId });
  const calc = useMutation({ mutationFn: () => api(`/api/exams/${examId}/calculate-results`, { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["results", examId] }) });
  const exp = useMutation({ mutationFn: () => downloadFile(`/api/exams/${examId}/results/export.csv`, "results.csv") });
  return <div><PageTitle title="Results" sub="Reviewed answers use the reviewer score; all others use the faculty score. AI scores never count." actions={<><Button variant="secondary" disabled={!examId || calc.isPending} onClick={() => calc.mutate()}>Save final scores</Button><Button disabled={!examId || exp.isPending} onClick={() => exp.mutate()}>Export CSV</Button></>} />
    <Card actions={<div className="w-64"><ExamPicker value={examId} onChange={setExamId} /></div>}>
      {!examId ? <Empty title="Select an examination" /> : q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data.results.length ? <Empty title="No results yet" hint="Results appear once answer sheets exist." /> :
        <Table head={["Register no.", "Student", ...q.data.questions.map((x: any) => `Q${x.question_number} /${x.max_marks}`), "Total", "Max", "%", "Status"]}>{q.data.results.map((r: any) => <tr key={r.student_id}>
          <Td className="font-mono">{r.register_number}</Td><Td>{r.name}</Td>
          {r.questions.map((x: any) => <Td key={x.question_number}>{x.marks ?? "–"}{x.source === "REVIEWER" && <span title={`Reviewed (faculty gave ${x.faculty_marks})`} className="ml-1 text-xs text-violet-600">R</span>}{x.review_pending && <span title="Review pending" className="ml-1 text-xs text-amber-600">⏳</span>}</Td>)}
          <Td className="font-semibold">{r.total_marks}</Td><Td>{r.maximum_marks}</Td><Td>{r.percentage}</Td><Td><Badge>{r.status}</Badge></Td></tr>)}</Table>}
      {(calc.error || exp.error) && <div className="mt-3"><ErrorBox error={calc.error || exp.error} /></div>}
      {calc.isSuccess && <p className="mt-3 text-sm text-emerald-700">Final scores saved to the database.</p>}</Card></div>;
}

export function Analytics() {
  const [examId, setExamId] = useState("");
  const q = useQuery({ queryKey: ["analytics", examId], queryFn: () => api<any>(`/api/analytics/exams/${examId}`), enabled: !!examId });
  const d = q.data;
  return <div><PageTitle title="Analytics" sub="Derived from stored records. Patterns are indicators for review, not evidence of intent." actions={<div className="w-64"><ExamPicker value={examId} onChange={setExamId} /></div>} />
    {!examId ? <Empty title="Select an examination" /> : q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : <>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4"><Stat label="Students" value={d.students} /><Stat label="Evaluated answers" value={`${d.evaluated_answers}/${d.answers}`} sub={`${d.completion_rate}% complete`} />
        <Stat label="Average total" value={d.average_total_marks ?? "–"} /><Stat label="Average %" value={d.average_percentage != null ? `${d.average_percentage}%` : "–"} /></div>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <Card title="Score distribution"><div style={{ height: 240 }}><ResponsiveContainer><BarChart data={d.score_distribution}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="range" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="students" fill="#4f46e5" /></BarChart></ResponsiveContainer></div><p className="mt-1 text-xs text-slate-500">Requires saved final scores (Results → Save final scores; also updated automatically on submission/review).</p></Card>
        <Card title="Question statistics (average %)"><div style={{ height: 240 }}><ResponsiveContainer><BarChart data={d.question_stats.map((s: any) => ({ ...s, q: `Q${s.question_number}` }))}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="q" /><YAxis domain={[0, 100]} /><Tooltip /><Bar dataKey="average_pct" name="Average %" fill="#10b981" /></BarChart></ResponsiveContainer></div></Card>
        <Card title="Faculty workload"><div style={{ height: 240 }}><ResponsiveContainer><BarChart data={d.faculty_workload}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Legend /><Bar dataKey="active" name="Active" fill="#4f46e5" /><Bar dataKey="completed" name="Completed" fill="#10b981" /></BarChart></ResponsiveContainer></div></Card>
        <Card title="Discrepancy cases">{!d.discrepancy_distribution.length ? <Empty title="No review cases" /> : <Table head={["Priority", "Status", "Count"]}>{d.discrepancy_distribution.map((r: any, i: number) => <tr key={i}><Td><Badge>{r.priority}</Badge></Td><Td><Badge>{r.status}</Badge></Td><Td>{r.count}</Td></tr>)}</Table>}</Card></div>
      <Card className="mt-6" title="Evaluation patterns (faculty vs AI reference)">{!d.evaluation_patterns.length ? <Empty title="No evaluations yet" /> : <>
        <Table head={["Faculty", "Evaluated", "Compared w/ AI", "Mean diff (faculty − AI)", "Mean |diff|", "Discrepancy flags", "Flag rate", "Mean awarded %"]}>{d.evaluation_patterns.map((p: any) => <tr key={p.faculty_id}><Td>{p.name}</Td><Td>{p.evaluated}</Td><Td>{p.compared_with_ai}</Td><Td>{p.mean_difference_vs_ai ?? "–"}</Td><Td>{p.mean_abs_difference_vs_ai ?? "–"}</Td><Td>{p.discrepancy_flags}</Td><Td>{p.discrepancy_rate_pct}%</Td><Td>{p.mean_awarded_pct}%</Td></tr>)}</Table>
        <p className="mt-2 text-xs text-slate-500">These indicate evaluation patterns relative to an imperfect AI reference. They are prompts for moderation, never proof of bias; small samples are not meaningful.</p></>}</Card></>}</div>;
}

export function AuditLogs() {
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ["audit", action, offset], queryFn: () => api<any>(`/api/audit-logs?limit=50&offset=${offset}${action ? `&action=${encodeURIComponent(action)}` : ""}`) });
  return <div><PageTitle title="Audit logs" sub="Passwords, tokens and secrets are never recorded." />
    <Card actions={<Input aria-label="Action prefix" className="w-56" placeholder="Filter action (e.g. evaluation)" value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }} />}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data.items.length ? <Empty title="No audit events" /> : <>
        <Table head={["Time", "User", "Action", "Entity", "Details"]}>{q.data.items.map((l: any) => <tr key={l.id}><Td className="whitespace-nowrap text-xs">{new Date(l.created_at).toLocaleString()}</Td><Td className="text-xs">{l.user_email || "system"}</Td><Td><Badge tone="blue">{l.action}</Badge></Td><Td className="text-xs">{l.entity_type}</Td><Td className="max-w-md truncate font-mono text-xs">{l.metadata ? JSON.stringify(l.metadata) : ""}</Td></tr>)}</Table>
        <div className="mt-3 flex items-center justify-between text-sm"><span>{offset + 1}–{Math.min(offset + 50, q.data.total)} of {q.data.total}</span><div className="flex gap-2"><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><Button variant="secondary" disabled={offset + 50 >= q.data.total} onClick={() => setOffset(offset + 50)}>Next</Button></div></div></>}</Card></div>;
}

export function SettingsPage() {
  const qc = useQueryClient();
  const s = useQuery({ queryKey: ["settings"], queryFn: () => api<any>("/api/settings") });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: () => api<any>("/api/settings/ai-status") });
  const [form, setForm] = useState<any | null>(null);
  const v = form ?? s.data;
  const save = useMutation({ mutationFn: () => api("/api/settings", { method: "PUT", body: { review_absolute_threshold: Number(v.review_absolute_threshold), review_relative_threshold: Number(v.review_relative_threshold), review_mode: v.review_mode, ai_low_confidence: Number(v.ai_low_confidence), blind_evaluation: !!v.blind_evaluation } }), onSuccess: () => { setForm(null); qc.invalidateQueries({ queryKey: ["settings"] }); } });
  if (s.isLoading) return <Spinner />;
  if (s.error) return <ErrorBox error={s.error} />;
  const set = (k: string, val: any) => setForm({ ...v, [k]: val });
  return <div><PageTitle title="Settings" sub="Backend-enforced configuration (stored in the database)." />
    <Card title="Discrepancy detection & evaluation"><div className="grid max-w-xl gap-3">
      <Field label="Review mode" hint="absolute = marks, relative = fraction of max marks, either = whichever triggers first"><Select value={v.review_mode} onChange={(e) => set("review_mode", e.target.value)}><option>absolute</option><option>relative</option><option>either</option></Select></Field>
      <Field label="Absolute threshold (marks)" hint="A review case is created when |faculty − AI| ≥ this value"><Input type="number" step="0.5" value={v.review_absolute_threshold} onChange={(e) => set("review_absolute_threshold", e.target.value)} /></Field>
      <Field label="Relative threshold (fraction of max marks)"><Input type="number" step="0.05" value={v.review_relative_threshold} onChange={(e) => set("review_relative_threshold", e.target.value)} /></Field>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!v.blind_evaluation} onChange={(e) => set("blind_evaluation", e.target.checked)} /> Blind evaluation (faculty see anonymous candidate codes)</label>
      {save.error && <ErrorBox error={save.error} />}<div><Button disabled={!form || save.isPending} onClick={() => save.mutate()}>Save settings</Button></div></div></Card>
    <Card className="mt-6" title="AI similarity engine">{ai.data && <p className="text-sm">Active provider: <b>{ai.data.provider}</b> {ai.data.fallback && <Badge tone="yellow">fallback</Badge>}
      {ai.data.fallback && <span className="block text-xs text-slate-500">The sentence-transformer model could not be loaded ({ai.data.load_error || "not configured"}); a scikit-learn TF-IDF similarity is used and recorded on each evaluation.</span>}</p>}</Card></div>;
}
