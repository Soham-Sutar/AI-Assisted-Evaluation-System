import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { useAuth } from "../../auth/AuthContext";
import { validateMarks } from "../../lib/validation";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, PageTitle, Select, Spinner, Stat, Table, Td, Textarea } from "../../components/ui";
import { ImageViewer } from "../../components/ImageViewer";

export function ReviewQueue({ base }: { base: "/reviewer" | "/admin" }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const q = useQuery({ queryKey: ["reviews", status, priority], queryFn: () => api<any[]>(`/api/reviews?${new URLSearchParams({ ...(status && { status }), ...(priority && { priority }) })}`) });
  const reviewers = useQuery({ queryKey: ["reviewers"], queryFn: () => api<any[]>("/api/faculty/reviewers"), enabled: user?.role === "ADMIN" });
  const assign = useMutation({ mutationFn: (v: { id: string; reviewer_id: string }) => api(`/api/reviews/${v.id}/assign`, { body: { reviewer_id: v.reviewer_id } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }) });
  return <div><PageTitle title="Review queue" sub="Answers where independent signals differ. A discrepancy is a prompt for review, not evidence of intent." />
    <Card actions={<><Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option>OPEN</option><option>ASSIGNED</option><option>RESOLVED</option><option>ESCALATED</option></Select>
      <Select aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)}><option value="">All priorities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></Select></>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title="No review cases" hint="Cases appear when faculty and AI scores differ beyond the configured threshold." /> :
        <Table head={["Student", "Q", "Faculty", "AI", "Diff", "Priority", "Reason", "Status", "Reviewer", ""]}>{q.data.map((c) => <tr key={c.id}>
          <Td>{c.register_number}</Td><Td>Q{c.question_number}</Td><Td>{c.faculty_marks ?? "–"}/{c.max_marks}</Td><Td>{c.ai_marks ?? "n/a"}</Td><Td>{c.discrepancy_value ?? "–"}</Td>
          <Td><Badge>{c.priority}</Badge></Td><Td className="text-xs">{c.trigger_label}</Td><Td><Badge>{c.status}</Badge></Td>
          <Td>{user?.role === "ADMIN" && c.status !== "RESOLVED" ? <select aria-label="Assign reviewer" className="rounded border px-1 py-0.5 text-xs" value={c.reviewer_id || ""} onChange={(e) => e.target.value && assign.mutate({ id: c.id, reviewer_id: e.target.value })}>
            <option value="">Unassigned</option>{reviewers.data?.map((r) => <option key={r.id} value={r.id}>{r.full_name}</option>)}</select> : (c.reviewer_name || "–")}</Td>
          <Td><Link className="text-brand-600" to={`${base}/review/${c.id}`}>Open</Link></Td></tr>)}</Table>}
      {assign.error && <div className="mt-3"><ErrorBox error={assign.error} /></div>}
    </Card></div>;
}

export function ReviewerDashboard() {
  const q = useQuery({ queryKey: ["reviews", "", ""], queryFn: () => api<any[]>("/api/reviews") });
  const n = (s: string) => q.data?.filter((c) => c.status === s).length ?? 0;
  return <div><PageTitle title="Reviewer dashboard" />
    {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Stat label="Open" value={n("OPEN")} /><Stat label="Assigned" value={n("ASSIGNED")} /><Stat label="Escalated" value={n("ESCALATED")} /><Stat label="Resolved" value={n("RESOLVED")} /></div>}
    <div className="mt-6"><Link to="/reviewer/reviews"><Button>Go to review queue</Button></Link></div></div>;
}

export function ReviewDetail({ base }: { base: "/reviewer" | "/admin" }) {
  const { reviewId } = useParams();
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["review", reviewId], queryFn: () => api<any>(`/api/reviews/${reviewId}`) });
  const [marks, setMarks] = useState("");
  const [comments, setComments] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const done = () => { qc.invalidateQueries({ queryKey: ["review", reviewId] }); qc.invalidateQueries({ queryKey: ["reviews"] }); };
  const resolve = useMutation({ mutationFn: () => api(`/api/reviews/${reviewId}/resolve`, { body: { reviewer_marks: Number(marks), reviewer_comments: comments } }), onSuccess: () => { done(); nav(`${base}/reviews`); } });
  const escalate = useMutation({ mutationFn: () => api(`/api/reviews/${reviewId}/escalate`, { body: { comments } }), onSuccess: done });
  const c = q.data;
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  const resolved = c.status === "RESOLVED";
  const submit = () => { const e = validateMarks(marks, c.max_marks, true) || (!comments.trim() ? "A review comment is required" : null); setErr(e); if (!e) resolve.mutate(); };
  const ai = c.ai_evaluation;
  return <div>
    <PageTitle title={`Review · ${c.register_number} · Q${c.question_number}`} sub={`${c.examination_name} · max ${c.max_marks} marks`} actions={<><Badge>{c.priority}</Badge><Badge>{c.status}</Badge><Link to={`${base}/reviews`}><Button variant="secondary">← Queue</Button></Link></>} />
    {c.note && <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{c.note}</p>}
    <div className="grid gap-5 lg:grid-cols-5">
      <Card className="lg:col-span-3" title="Original answer"><ImageViewer src={`/api/answers/${c.answer_id}/image`} /></Card>
      <div className="space-y-4 lg:col-span-2">
        <Card title="Scores"><div className="grid grid-cols-3 gap-3 text-center">
          <div><p className="text-xs text-slate-500">Faculty</p><p className="text-xl font-bold">{c.faculty_marks ?? "–"}</p></div>
          <div><p className="text-xs text-slate-500">AI reference</p><p className="text-xl font-bold">{c.ai_marks ?? "n/a"}</p></div>
          <div><p className="text-xs text-slate-500">Difference</p><p className="text-xl font-bold">{c.discrepancy_value ?? "–"}</p></div></div>
          {c.faculty_evaluation?.comments && <p className="mt-3 text-sm"><b>Faculty comment ({c.faculty_evaluation.faculty_name}):</b> {c.faculty_evaluation.comments}</p>}
          {ai && ai.status === "COMPLETED" && <div className="mt-3 text-xs text-slate-600"><p>AI confidence {Math.round((ai.confidence_score || 0) * 100)}% · semantic {ai.semantic_similarity} · key-points {ai.keypoint_score} · {ai.model_name}</p>
            {ai.explanation?.keypoints?.map((k: any, i: number) => <p key={i} className="mt-1 border-t pt-1"><Badge tone={k.status === "covered" ? "green" : k.status === "not covered" ? "red" : "yellow"}>{k.status}</Badge> {k.description} <span className="text-slate-400">({k.marks})</span></p>)}</div>}
          {ai?.status === "FAILED" && <p className="mt-3 text-xs text-amber-700">AI unavailable: {ai.error_message}</p>}</Card>
        <Card title="Reference"><p className="text-sm font-medium">{c.question_text}</p><p className="mt-2 text-sm text-slate-700">{c.model_answer_text || "No model answer."}</p>
          {c.rubric?.points?.map((p: any, i: number) => <p key={i} className="flex justify-between border-t pt-1 text-sm"><span>{p.description}</span><b>{p.marks}</b></p>)}</Card>
        <Card title={<span>OCR text <Badge>{c.ocr_status}</Badge></span>}><p className="whitespace-pre-wrap text-sm text-slate-700">{c.extracted_text || "(no text extracted)"}</p></Card>
        <Card title="Review decision">
          {resolved ? <p className="text-sm">Resolved with <b>{c.reviewer_marks}</b> marks by {c.reviewer_name}. {c.reviewer_comments}</p> : <div className="space-y-3">
            <Field label={`Review marks (0 – ${c.max_marks})`} error={err || undefined}><Input type="number" step="0.5" aria-label="Review marks" value={marks} onChange={(e) => { setMarks(e.target.value); setErr(null); }} /></Field>
            <Field label="Comments (required)"><Textarea rows={3} value={comments} onChange={(e) => setComments(e.target.value)} /></Field>
            {(resolve.error || escalate.error) && <ErrorBox error={resolve.error || escalate.error} />}
            <div className="flex gap-2"><Button onClick={submit} disabled={resolve.isPending}>Resolve with this score</Button><Button variant="secondary" onClick={() => escalate.mutate()} disabled={escalate.isPending}>Escalate</Button></div>
            <p className="text-xs text-slate-500">The reviewer score replaces the faculty score for this answer. The AI score is never used as the final mark.</p></div>}</Card>
      </div></div></div>;
}
