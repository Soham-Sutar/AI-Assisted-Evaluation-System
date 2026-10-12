import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { validateMarks } from "../../lib/validation";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, PageTitle, Spinner, Stat, Table, Td, Textarea } from "../../components/ui";
import { ImageViewer } from "../../components/ImageViewer";

export function FacultyDashboard() {
  const sum = useQuery({ queryKey: ["fac-summary"], queryFn: () => api("/api/faculty/me/summary") });
  const list = useQuery({ queryKey: ["fac-assignments"], queryFn: () => api<any[]>("/api/faculty/me/assignments") });
  const next = list.data?.find((a) => a.status !== "COMPLETED");
  return <div>
    <PageTitle title="My dashboard" sub="Answers assigned to you for independent evaluation" />
    {sum.isLoading ? <Spinner /> : sum.error ? <ErrorBox error={sum.error} /> : <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Stat label="Pending" value={sum.data.pending} /><Stat label="In progress" value={sum.data.in_progress} />
      <Stat label="Completed" value={sum.data.completed} /><Stat label="Progress" value={`${sum.data.progress_pct}%`} /></div>}
    <Card className="mt-6" title="Next up" actions={<Link className="text-sm text-brand-600" to="/faculty/assignments">All assignments →</Link>}>
      {next ? <div className="flex items-center justify-between"><p className="text-sm">Question {next.question_number} · {next.examination_name} · <span className="text-slate-500">{next.candidate_code}</span></p>
        <Link to={`/faculty/evaluate/${next.answer_id}`}><Button>Start evaluating</Button></Link></div> : <Empty title="Nothing pending" hint="New assignments appear here once the admin runs assignment." />}
    </Card></div>;
}

export function FacultyAssignments() {
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["fac-assignments", status], queryFn: () => api<any[]>(`/api/faculty/me/assignments${status ? `?status=${status}` : ""}`) });
  return <div><PageTitle title="My assignments" sub="You only see answers assigned to you. Candidates are anonymised." />
    <Card actions={<select aria-label="Filter status" className="rounded border px-2 py-1 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
      <option value="">All</option><option value="ASSIGNED">Assigned</option><option value="IN_PROGRESS">In progress</option><option value="COMPLETED">Completed</option></select>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title="No assignments" /> :
        <Table head={["Question", "Candidate", "Exam", "Max marks", "Status", "Assigned", ""]}>{q.data.map((a) => <tr key={a.assignment_id}>
          <Td>Q{a.question_number}</Td><Td className="font-mono text-xs">{a.candidate_code}</Td><Td>{a.examination_name}</Td><Td>{a.max_marks}</Td><Td><Badge>{a.status}</Badge></Td>
          <Td>{new Date(a.assigned_at).toLocaleString()}</Td><Td><Link className="text-brand-600" to={`/faculty/evaluate/${a.answer_id}`}>{a.status === "COMPLETED" ? "View" : "Evaluate"}</Link></Td></tr>)}</Table>}
    </Card></div>;
}

export function FacultyEvaluate() {
  const { answerId } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["answer", answerId], queryFn: () => api<any>(`/api/answers/${answerId}`) });
  const a = q.data;
  const locked = !!a?.my_evaluation && a.my_evaluation.is_draft === false;
  const [marks, setMarks] = useState("");
  const [comments, setComments] = useState("");
  const [ocr, setOcr] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [showModel, setShowModel] = useState(false);
  useEffect(() => {
    if (!a) return;
    setMarks(a.my_evaluation?.marks_awarded != null ? String(a.my_evaluation.marks_awarded) : "");
    setComments(a.my_evaluation?.comments || ""); setOcr(a.extracted_text || "");
  }, [a?.id, a?.my_evaluation?.id, a?.my_evaluation?.is_draft]);
  const save = useMutation({
    mutationFn: (submit: boolean) => api("/api/evaluations", { body: { answer_id: answerId, marks_awarded: marks.trim() === "" ? null : Number(marks), comments, submit } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["answer", answerId] }); qc.invalidateQueries({ queryKey: ["fac-assignments"] }); qc.invalidateQueries({ queryKey: ["fac-summary"] }); },
  });
  const saveOcr = useMutation({ mutationFn: () => api(`/api/answers/${answerId}/ocr-text`, { method: "PUT", body: { text: ocr } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["answer", answerId] }) });
  const act = (submit: boolean) => { const err = validateMarks(marks, a.max_marks, submit); setFieldError(err); if (!err) save.mutate(submit); };

  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  return <div>
    <PageTitle title={`Question ${a.question_number} · ${a.candidate_code}`} sub={`${a.examination_name} · ${a.subject} · Maximum marks ${a.max_marks}`} actions={<Link to="/faculty/assignments"><Button variant="secondary">← Back</Button></Link>} />
    <div className="grid gap-5 lg:grid-cols-5">
      <Card className="lg:col-span-3" title="Answer"><ImageViewer src={`/api/answers/${answerId}/image`} />
        {a.page_start !== a.page_end && <p className="mt-2 text-xs text-slate-500">This answer continues across pages {a.page_start}–{a.page_end} (shown stacked).</p>}</Card>
      <div className="space-y-4 lg:col-span-2">
        <Card title="Your evaluation">
          <p className="mb-2 text-sm font-medium">{a.question_text}</p>
          <div className="space-y-3">
            <Field label={`Marks (0 – ${a.max_marks})`} error={fieldError || undefined}>
              <Input type="number" step="0.5" min={0} max={a.max_marks} value={marks} disabled={locked} aria-label="Marks" onChange={(e) => { setMarks(e.target.value); setFieldError(null); }} /></Field>
            <Field label="Comments"><Textarea rows={3} value={comments} disabled={locked} onChange={(e) => setComments(e.target.value)} /></Field>
            {save.error && <ErrorBox error={save.error} />}
            {locked ? <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">Submitted {new Date(a.my_evaluation.submitted_at).toLocaleString()} — evaluation is locked.</p> :
              <div className="flex gap-2"><Button variant="secondary" onClick={() => act(false)} disabled={save.isPending}>Save draft</Button>
                <Button onClick={() => act(true)} disabled={save.isPending}>Submit evaluation</Button></div>}
            {!locked && <p className="text-xs text-slate-500">The AI reference score is revealed only after you submit your own evaluation, to avoid anchoring.</p>}
          </div></Card>
        {a.ai_evaluation && locked && <Card title="AI reference (advisory)">
          {a.ai_evaluation.status === "COMPLETED" ? <div className="space-y-1 text-sm">
            <p>AI reference score: <b>{a.ai_evaluation.ai_marks}</b> / {a.max_marks} <span className="text-slate-500">(confidence {Math.round((a.ai_evaluation.confidence_score || 0) * 100)}%)</span></p>
            <p className="text-xs text-slate-500">Your score is final unless a review is triggered; the AI score never replaces it. Method: {a.ai_evaluation.model_name}</p></div>
            : <p className="text-sm text-amber-700">AI reference unavailable: {a.ai_evaluation.error_message}. Your evaluation is unaffected.</p>}</Card>}
        {locked && !a.ai_evaluation && <p className="text-xs text-slate-500">AI reference is being generated… refresh in a moment.</p>}
        <Card title={<span>OCR text <Badge>{a.ocr_status}</Badge> {a.ocr_corrected && <Badge tone="blue">corrected</Badge>}</span>}>
          {a.ocr_status === "LOW_CONFIDENCE" || a.ocr_status === "FAILED" ? <p className="mb-2 text-xs text-amber-700">OCR confidence is low ({a.ocr_confidence ?? "n/a"}). Judge from the image; correct the text if you want the AI reference to use it.</p> : null}
          <Textarea rows={6} value={ocr} disabled={locked} aria-label="OCR text" onChange={(e) => setOcr(e.target.value)} />
          {!locked && <Button className="mt-2" variant="secondary" onClick={() => saveOcr.mutate()} disabled={saveOcr.isPending}>Save OCR correction</Button>}</Card>
        <Card title="Model answer & rubric" actions={<Button variant="ghost" onClick={() => setShowModel((s) => !s)}>{showModel ? "Hide" : "Show"}</Button>}>
          {showModel ? <div className="space-y-2 text-sm"><p>{a.model_answer_text || "No model answer configured."}</p>
            {a.rubric?.points?.map((p: any, i: number) => <p key={i} className="flex justify-between border-t pt-1"><span>{p.description}</span><b>{p.marks}</b></p>)}</div> : <p className="text-xs text-slate-500">Expand to view.</p>}</Card>
      </div></div></div>;
}
