import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../../lib/api";
import { Badge, Button, Card, Confirm, Empty, ErrorBox, Field, Input, Modal, PageTitle, Select, Spinner, Stat, Table, Td, Textarea } from "../../components/ui";

export function AdminDashboard() {
  const q = useQuery({ queryKey: ["overview"], queryFn: () => api<any>("/api/analytics/overview") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  return <div><PageTitle title="Admin dashboard" sub="All figures are computed live from the database." />
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Stat label="Students" value={d.total_students} /><Stat label="Answer sheets" value={d.total_answer_sheets} sub={`${d.processed_sheets} processed`} />
      <Stat label="Segmented answers" value={d.total_answers} sub={`${d.answers_needing_correction} need correction`} /><Stat label="Evaluation completion" value={`${d.evaluation_completion_rate}%`} />
      <Stat label="Pending evaluations" value={d.pending_evaluations} /><Stat label="Completed evaluations" value={d.completed_evaluations} />
      <Stat label="Flagged discrepancies" value={d.flagged_discrepancies} sub={`${d.open_reviews} open`} /><Stat label="Resolved reviews" value={d.resolved_reviews} /></div>
    <Card className="mt-6" title="Faculty workload">{!d.faculty_workload.length ? <Empty title="No faculty yet" /> : <div style={{ height: 260 }}><ResponsiveContainer><BarChart data={d.faculty_workload}>
      <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="active" name="Active" fill="#4f46e5" /><Bar dataKey="completed" name="Completed" fill="#10b981" /></BarChart></ResponsiveContainer></div>}</Card>
    <div className="mt-6 grid gap-3 text-sm md:grid-cols-3">{[["/admin/answersheets", "Upload answer sheets"], ["/admin/segmentation", "Review segmentation"], ["/admin/assignments", "Assign to faculty"]].map(([to, l]) => <Link key={to} to={to} className="rounded-lg border bg-white p-4 text-brand-600 shadow-sm hover:bg-brand-50">{l} →</Link>)}</div></div>;
}

const examSchema = z.object({ name: z.string().min(2, "Name is required"), academic_year: z.string().min(4, "e.g. 2026-27"), semester: z.string().min(1, "Required"), subject_id: z.string().min(1, "Choose a subject"), exam_date: z.string().optional() });

export function Exams() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [subjOpen, setSubjOpen] = useState(false);
  const exams = useQuery({ queryKey: ["exams"], queryFn: () => api<any[]>("/api/exams") });
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: () => api<any[]>("/api/subjects") });
  const { register, handleSubmit, reset, formState: { errors } } = useForm<z.infer<typeof examSchema>>({ resolver: zodResolver(examSchema) });
  const create = useMutation({ mutationFn: (v: any) => api("/api/exams", { body: { ...v, exam_date: v.exam_date || null } }), onSuccess: () => { setOpen(false); reset(); qc.invalidateQueries({ queryKey: ["exams"] }); } });
  return <div><PageTitle title="Examinations" actions={<><Button variant="secondary" onClick={() => setSubjOpen(true)}>New subject</Button><Button onClick={() => setOpen(true)}>New examination</Button></>} />
    <Card>{exams.isLoading ? <Spinner /> : exams.error ? <ErrorBox error={exams.error} /> : !exams.data?.length ? <Empty title="No examinations" hint="Create a subject, then an examination." /> :
      <Table head={["Name", "Subject", "Year / Sem", "Questions", "Total marks", "Status", ""]}>{exams.data.map((e) => <tr key={e.id}><Td className="font-medium">{e.name}</Td><Td>{e.subject_name}</Td><Td>{e.academic_year} / {e.semester}</Td>
        <Td>{e.question_count}</Td><Td>{e.total_marks}</Td><Td><Badge>{e.status}</Badge></Td><Td><Link className="text-brand-600" to={`/admin/exams/${e.id}`}>Open</Link></Td></tr>)}</Table>}</Card>
    {open && <Modal title="New examination" onClose={() => setOpen(false)}><form className="space-y-3" onSubmit={handleSubmit((v) => create.mutate(v))}>
      <Field label="Name" error={errors.name?.message}><Input {...register("name")} /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Academic year" error={errors.academic_year?.message}><Input placeholder="2026-27" {...register("academic_year")} /></Field><Field label="Semester" error={errors.semester?.message}><Input {...register("semester")} /></Field></div>
      <Field label="Subject" error={errors.subject_id?.message}><Select {...register("subject_id")}><option value="">Select…</option>{subjects.data?.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}</Select></Field>
      <Field label="Exam date"><Input type="date" {...register("exam_date")} /></Field>
      {create.error && <ErrorBox error={create.error} />}<div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" disabled={create.isPending}>Create</Button></div></form></Modal>}
    {subjOpen && <SubjectModal onClose={() => setSubjOpen(false)} />}</div>;
}

function SubjectModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [v, setV] = useState({ name: "", code: "", description: "" });
  const m = useMutation({ mutationFn: () => api("/api/subjects", { body: v }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["subjects"] }); onClose(); } });
  return <Modal title="New subject" onClose={onClose}><div className="space-y-3"><Field label="Name"><Input value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} /></Field>
    <Field label="Code"><Input value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} /></Field><Field label="Description"><Input value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} /></Field>
    {m.error && <ErrorBox error={m.error} />}<div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={m.isPending} onClick={() => m.mutate()}>Create</Button></div></div></Modal>;
}

export function ExamDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<any | null>(null);
  const [del, setDel] = useState<any | null>(null);
  const exam = useQuery({ queryKey: ["exam", id], queryFn: () => api<any>(`/api/exams/${id}`) });
  const qs = useQuery({ queryKey: ["questions", id], queryFn: () => api<any[]>(`/api/exams/${id}/questions`) });
  const status = useMutation({ mutationFn: (s: string) => api(`/api/exams/${id}`, { method: "PUT", body: { name: exam.data.name, academic_year: exam.data.academic_year, semester: exam.data.semester, subject_id: exam.data.subject_id, exam_date: exam.data.exam_date, status: s } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["exam", id] }) });
  const remove = useMutation({ mutationFn: (qid: string) => api(`/api/questions/${qid}`, { method: "DELETE" }), onSuccess: () => { setDel(null); qc.invalidateQueries({ queryKey: ["questions", id] }); qc.invalidateQueries({ queryKey: ["exam", id] }); } });
  if (exam.isLoading) return <Spinner />;
  if (exam.error) return <ErrorBox error={exam.error} />;
  const e = exam.data;
  return <div><PageTitle title={e.name} sub={`${e.subject_name} · ${e.academic_year} · Semester ${e.semester}`} actions={<><Badge>{e.status}</Badge>{e.status === "DRAFT" && <Button variant="secondary" onClick={() => status.mutate("READY")}>Mark ready</Button>}</>} />
    <div className="mb-5 grid grid-cols-2 gap-4 md:grid-cols-4"><Stat label="Questions" value={e.question_count} /><Stat label="Total marks" value={e.total_marks} /><Stat label="Answer sheets" value={e.sheet_count} /><Stat label="Segmented answers" value={e.answer_count} /></div>
    <Card title="Questions, model answers & rubrics" actions={<Button onClick={() => setEditing({})}>Add question</Button>}>
      {qs.isLoading ? <Spinner /> : qs.error ? <ErrorBox error={qs.error} /> : !qs.data?.length ? <Empty title="No questions" hint="Add questions with maximum marks and a model answer." /> :
        <div className="space-y-3">{qs.data.map((q) => <div key={q.id} className="rounded-lg border p-3"><div className="flex items-start justify-between gap-3"><div><p className="font-medium">Q{q.question_number}. {q.question_text} <span className="text-slate-500">({q.max_marks} marks)</span></p>
          <p className="mt-1 text-sm text-slate-600">{q.model_answer_text || <i>No model answer yet</i>}</p>
          {q.rubric?.points && <ul className="mt-1 text-xs text-slate-500">{q.rubric.points.map((p: any, i: number) => <li key={i}>• {p.description} — {p.marks}</li>)}</ul>}</div>
          <div className="flex gap-1"><Button variant="secondary" onClick={() => setEditing(q)}>Edit</Button><Button variant="ghost" onClick={() => setDel(q)}>Delete</Button></div></div></div>)}</div>}
      {remove.error && <div className="mt-3"><ErrorBox error={remove.error} /></div>}</Card>
    {editing && <QuestionModal examId={id!} q={editing} onClose={() => setEditing(null)} />}
    {del && <Confirm message={`Delete Q${del.question_number}? This cannot be undone.`} onCancel={() => setDel(null)} onConfirm={() => remove.mutate(del.id)} />}</div>;
}

function QuestionModal({ examId, q, onClose }: { examId: string; q: any; onClose: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ question_number: String(q.question_number ?? ""), question_text: q.question_text ?? "", max_marks: String(q.max_marks ?? ""), model_answer_text: q.model_answer_text ?? "" });
  const [points, setPoints] = useState<{ description: string; marks: string }[]>((q.rubric?.points || []).map((p: any) => ({ description: p.description, marks: String(p.marks) })));
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => {
      const body = { question_number: Number(f.question_number), question_text: f.question_text, max_marks: Number(f.max_marks), model_answer_text: f.model_answer_text || null,
        rubric: points.length ? { points: points.map((p) => ({ description: p.description, marks: Number(p.marks) })) } : null };
      return q.id ? api(`/api/questions/${q.id}`, { method: "PUT", body }) : api(`/api/exams/${examId}/questions`, { body });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["questions", examId] }); qc.invalidateQueries({ queryKey: ["exam", examId] }); onClose(); } });
  const total = points.reduce((s, p) => s + (Number(p.marks) || 0), 0);
  const submit = () => {
    if (!f.question_number || !f.question_text.trim() || !(Number(f.max_marks) > 0)) return setErr("Question number, text and positive maximum marks are required");
    if (total > Number(f.max_marks)) return setErr(`Rubric marks (${total}) exceed the maximum (${f.max_marks})`);
    if (points.some((p) => !p.description.trim() || !(Number(p.marks) > 0))) return setErr("Each rubric point needs a description and positive marks");
    setErr(null); m.mutate();
  };
  return <Modal title={q.id ? `Edit Q${q.question_number}` : "Add question"} onClose={onClose}><div className="space-y-3">
    <div className="grid grid-cols-2 gap-3"><Field label="Question number"><Input type="number" value={f.question_number} onChange={(e) => setF({ ...f, question_number: e.target.value })} /></Field>
      <Field label="Maximum marks"><Input type="number" step="0.5" value={f.max_marks} onChange={(e) => setF({ ...f, max_marks: e.target.value })} /></Field></div>
    <Field label="Question text"><Textarea rows={2} value={f.question_text} onChange={(e) => setF({ ...f, question_text: e.target.value })} /></Field>
    <Field label="Model answer" hint="Used by the AI reference evaluator."><Textarea rows={4} value={f.model_answer_text} onChange={(e) => setF({ ...f, model_answer_text: e.target.value })} /></Field>
    <div><div className="mb-1 flex items-center justify-between text-sm font-medium"><span>Rubric (optional) — {total}/{f.max_marks || 0} marks</span><Button variant="secondary" onClick={() => setPoints([...points, { description: "", marks: "" }])}>Add point</Button></div>
      {points.map((p, i) => <div key={i} className="mb-2 flex gap-2"><Input aria-label={`Rubric point ${i + 1}`} placeholder="Key point" value={p.description} onChange={(e) => setPoints(points.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
        <Input aria-label={`Rubric marks ${i + 1}`} className="w-20" type="number" step="0.5" value={p.marks} onChange={(e) => setPoints(points.map((x, j) => (j === i ? { ...x, marks: e.target.value } : x)))} />
        <Button variant="ghost" onClick={() => setPoints(points.filter((_, j) => j !== i))}>✕</Button></div>)}</div>
    {(err || m.error) && <ErrorBox error={err ? new Error(err) : m.error} />}
    <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={m.isPending} onClick={submit}>Save</Button></div></div></Modal>;
}

export function Students() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<any | null>(null);
  const [csv, setCsv] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["students", search], queryFn: () => api<any[]>(`/api/students${search ? `?search=${encodeURIComponent(search)}` : ""}`) });
  const imp = useMutation({ mutationFn: (file: File) => { const f = new FormData(); f.append("file", file); return api<any>("/api/students/import", { form: f }); }, onSuccess: (r) => { setCsv(`Imported ${r.created}; ${r.errors.length} skipped${r.errors.length ? ": " + r.errors.slice(0, 3).map((e: any) => `row ${e.row} ${e.error}`).join("; ") : ""}`); qc.invalidateQueries({ queryKey: ["students"] }); } });
  return <div><PageTitle title="Students" actions={<><label className="cursor-pointer rounded-md border bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50">Import CSV<input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && imp.mutate(e.target.files[0])} /></label><Button onClick={() => setOpen({})}>Add student</Button></>} />
    {csv && <p className="mb-3 text-sm text-emerald-700">{csv}</p>}{imp.error && <ErrorBox error={imp.error} />}
    <Card actions={<Input aria-label="Search students" className="w-64" placeholder="Search name / register no." value={search} onChange={(e) => setSearch(e.target.value)} />}>
      {list.isLoading ? <Spinner /> : list.error ? <ErrorBox error={list.error} /> : !list.data?.length ? <Empty title="No students found" /> :
        <Table head={["Register no.", "Name", "Division", "Email", ""]}>{list.data.map((s) => <tr key={s.id}><Td className="font-mono">{s.register_number}</Td><Td>{s.name}</Td><Td>{s.division}</Td><Td>{s.email}</Td><Td><Button variant="ghost" onClick={() => setOpen(s)}>Edit</Button></Td></tr>)}</Table>}</Card>
    {open && <StudentModal s={open} onClose={() => setOpen(null)} />}</div>;
}

function StudentModal({ s, onClose }: { s: any; onClose: () => void }) {
  const qc = useQueryClient();
  const [v, setV] = useState({ register_number: s.register_number || "", name: s.name || "", division: s.division || "", email: s.email || "" });
  const m = useMutation({ mutationFn: () => { const body = { ...v, division: v.division || null, email: v.email || null }; return s.id ? api(`/api/students/${s.id}`, { method: "PUT", body }) : api("/api/students", { body }); }, onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); onClose(); } });
  return <Modal title={s.id ? "Edit student" : "Add student"} onClose={onClose}><div className="space-y-3">
    {(["register_number", "name", "division", "email"] as const).map((k) => <Field key={k} label={k.replace("_", " ")}><Input value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></Field>)}
    {m.error && <ErrorBox error={m.error} />}<div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={m.isPending} onClick={() => m.mutate()}>Save</Button></div></div></Modal>;
}

export function FacultyAdmin() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<any | null>(null);
  const list = useQuery({ queryKey: ["faculty"], queryFn: () => api<any[]>("/api/faculty?include_reviewers=true") });
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: () => api<any[]>("/api/subjects") });
  const toggle = useMutation({ mutationFn: (f: any) => api(`/api/faculty/${f.id}`, { method: "PUT", body: { is_active: !f.is_active } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["faculty"] }) });
  return <div><PageTitle title="Faculty & reviewers" actions={<Button onClick={() => setOpen(true)}>Add user</Button>} />
    <Card>{list.isLoading ? <Spinner /> : list.error ? <ErrorBox error={list.error} /> : <Table head={["Name", "Email", "Role", "Subjects", "Workload", "Available", "Active", ""]}>{list.data?.map((f) => <tr key={f.id}>
      <Td>{f.full_name}</Td><Td>{f.email}</Td><Td><Badge>{f.role}</Badge></Td><Td className="text-xs">{f.subjects.join(", ") || "–"}</Td>
      <Td>{f.role === "FACULTY" ? `${f.current_assignment_count}/${f.max_active_assignments}` : "–"}</Td><Td>{f.role === "FACULTY" ? (f.is_available ? "Yes" : "No") : "–"}</Td><Td>{f.is_active ? "Yes" : "No"}</Td>
      <Td className="whitespace-nowrap">{f.role === "FACULTY" && <Button variant="ghost" onClick={() => setEdit(f)}>Eligibility</Button>}<Button variant="ghost" onClick={() => toggle.mutate(f)}>{f.is_active ? "Disable" : "Enable"}</Button></Td></tr>)}</Table>}
      {toggle.error && <ErrorBox error={toggle.error} />}</Card>
    {open && <NewUserModal subjects={subjects.data || []} onClose={() => setOpen(false)} />}
    {edit && <EligibilityModal f={edit} subjects={subjects.data || []} onClose={() => setEdit(null)} />}</div>;
}

function NewUserModal({ subjects, onClose }: { subjects: any[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [v, setV] = useState({ full_name: "", email: "", password: "", role: "FACULTY", max_active_assignments: "40" });
  const [subs, setSubs] = useState<string[]>([]);
  const m = useMutation({ mutationFn: () => api("/api/auth/register", { body: { ...v, max_active_assignments: Number(v.max_active_assignments), subject_ids: subs } }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["faculty"] }); onClose(); } });
  return <Modal title="Add user" onClose={onClose}><div className="space-y-3"><Field label="Full name"><Input value={v.full_name} onChange={(e) => setV({ ...v, full_name: e.target.value })} /></Field>
    <Field label="Email"><Input type="email" value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} /></Field><Field label="Password" hint="At least 8 characters"><Input type="password" value={v.password} onChange={(e) => setV({ ...v, password: e.target.value })} /></Field>
    <div className="grid grid-cols-2 gap-3"><Field label="Role"><Select value={v.role} onChange={(e) => setV({ ...v, role: e.target.value })}><option>FACULTY</option><option>REVIEWER</option></Select></Field>
      <Field label="Max active assignments"><Input type="number" value={v.max_active_assignments} onChange={(e) => setV({ ...v, max_active_assignments: e.target.value })} /></Field></div>
    {v.role === "FACULTY" && <fieldset><legend className="mb-1 text-sm font-medium">Subject eligibility</legend>{subjects.map((s) => <label key={s.id} className="mr-4 text-sm"><input type="checkbox" checked={subs.includes(s.id)} onChange={(e) => setSubs(e.target.checked ? [...subs, s.id] : subs.filter((x) => x !== s.id))} /> {s.name}</label>)}</fieldset>}
    {m.error && <ErrorBox error={m.error} />}<div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={m.isPending} onClick={() => m.mutate()}>Create</Button></div></div></Modal>;
}

function EligibilityModal({ f, subjects, onClose }: { f: any; subjects: any[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [subs, setSubs] = useState<string[]>(f.subject_ids);
  const [avail, setAvail] = useState(!!f.is_available);
  const [max, setMax] = useState(String(f.max_active_assignments ?? 50));
  const m = useMutation({ mutationFn: async () => { await api(`/api/faculty/${f.id}`, { method: "PUT", body: { subject_ids: subs } }); await api(`/api/faculty/${f.id}/availability`, { body: { is_available: avail, max_active_assignments: Number(max) } }); }, onSuccess: () => { qc.invalidateQueries({ queryKey: ["faculty"] }); onClose(); } });
  return <Modal title={`Eligibility – ${f.full_name}`} onClose={onClose}><div className="space-y-3">
    <fieldset><legend className="mb-1 text-sm font-medium">Subjects</legend>{subjects.map((s) => <label key={s.id} className="mr-4 text-sm"><input type="checkbox" checked={subs.includes(s.id)} onChange={(e) => setSubs(e.target.checked ? [...subs, s.id] : subs.filter((x) => x !== s.id))} /> {s.name}</label>)}</fieldset>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={avail} onChange={(e) => setAvail(e.target.checked)} /> Available for assignment</label>
    <Field label="Maximum active assignments"><Input type="number" value={max} onChange={(e) => setMax(e.target.value)} /></Field>
    {m.error && <ErrorBox error={m.error} />}<div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={m.isPending} onClick={() => m.mutate()}>Save</Button></div></div></Modal>;
}
