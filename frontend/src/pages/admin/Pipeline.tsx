import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Badge, Button, Card, Confirm, Empty, ErrorBox, Field, Input, Modal, PageTitle, Select, Spinner, Stat, Table, Td } from "../../components/ui";
import { ImageViewer } from "../../components/ImageViewer";
import { ExamPicker } from "./shared";

export function AnswerSheets() {
  const qc = useQueryClient();
  const [examId, setExamId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [single, setSingle] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [report, setReport] = useState<any[] | null>(null);
  const [mapFor, setMapFor] = useState<any | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const sheets = useQuery({ queryKey: ["sheets", examId], queryFn: () => api<any[]>(`/api/answer-sheets${examId ? `?exam_id=${examId}` : ""}`),
    refetchInterval: (q) => (q.state.data?.some((s: any) => s.processing_status === "PROCESSING") ? 2500 : false) });
  const students = useQuery({ queryKey: ["students", ""], queryFn: () => api<any[]>("/api/students") });
  const upload = useMutation({
    mutationFn: () => { const f = new FormData(); f.append("exam_id", examId); if (studentId) f.append("student_id", studentId); f.append("single_sheet", String(single)); f.append("auto_process", "true"); files.forEach((x) => f.append("files", x)); return api("/api/answer-sheets/upload", { form: f }); },
    onSuccess: (r: any) => { setReport(r.results); setFiles([]); qc.invalidateQueries({ queryKey: ["sheets"] }); },
  });
  const process = useMutation({ mutationFn: (id: string) => api(`/api/answer-sheets/${id}/process`, { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["sheets"] }) });
  const map = useMutation({ mutationFn: (v: { id: string; student_id: string }) => api(`/api/answer-sheets/${v.id}`, { method: "PATCH", body: { student_id: v.student_id } }), onSuccess: () => { setMapFor(null); qc.invalidateQueries({ queryKey: ["sheets"] }); } });
  const [pick, setPick] = useState("");
  const onDrop = (e: React.DragEvent) => { e.preventDefault(); setDrag(false); setFiles(Array.from(e.dataTransfer.files)); };
  return <div><PageTitle title="Answer sheets" sub="Upload scanned sheets (PNG/JPG/PDF). Name files by register number (e.g. 2022IS001.png) for automatic student mapping." />
    <Card title="Upload">
      <div className="grid gap-3 md:grid-cols-3"><Field label="Examination"><ExamPicker value={examId} onChange={setExamId} /></Field>
        <Field label="Student (optional, manual mapping)"><Select value={studentId} onChange={(e) => setStudentId(e.target.value)}><option value="">Map by filename</option>{students.data?.map((s) => <option key={s.id} value={s.id}>{s.register_number} — {s.name}</option>)}</Select></Field>
        <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={single} onChange={(e) => setSingle(e.target.checked)} /> All files are pages of ONE sheet</label></div>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop} onClick={() => input.current?.click()} role="button" tabIndex={0} aria-label="Drop files or click to choose"
        className={`mt-3 cursor-pointer rounded-lg border-2 border-dashed p-8 text-center text-sm ${drag ? "border-brand-500 bg-brand-50" : "border-slate-300"}`}>
        <input ref={input} type="file" multiple accept=".png,.jpg,.jpeg,.pdf" className="hidden" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
        {files.length ? <p>{files.length} file(s): {files.map((f) => f.name).join(", ")}</p> : <p className="text-slate-500">Drag & drop answer sheets here, or click to browse</p>}</div>
      {files.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{files.slice(0, 6).map((f) => f.type.startsWith("image/") ? <img key={f.name} alt={f.name} src={URL.createObjectURL(f)} className="h-20 rounded border" /> : null)}</div>}
      {upload.error && <div className="mt-3"><ErrorBox error={upload.error} /></div>}
      <Button className="mt-3" disabled={!examId || !files.length || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? "Uploading…" : "Upload & process"}</Button>
      {report && <ul className="mt-3 space-y-1 text-sm">{report.map((r, i) => <li key={i} className={r.status === "error" ? "text-red-700" : "text-emerald-700"}>{r.filename}: {r.status === "error" ? r.detail : `${r.status}${r.mapped ? ` → ${r.register_number}` : " (not mapped — map manually below)"}`}</li>)}</ul>}</Card>
    <Card className="mt-6" title="Uploaded sheets" actions={<div className="w-64"><ExamPicker value={examId} onChange={setExamId} /></div>}>
      {sheets.isLoading ? <Spinner /> : sheets.error ? <ErrorBox error={sheets.error} /> : !sheets.data?.length ? <Empty title="No answer sheets yet" /> :
        <Table head={["File", "Student", "Pages", "Status", "Answers", "Flagged", "Message", ""]}>{sheets.data.map((s) => <tr key={s.id}>
          <Td>{s.original_filename}</Td><Td>{s.register_number ? `${s.register_number} · ${s.student_name}` : <Badge tone="red">unmapped</Badge>}</Td><Td>{s.page_count}</Td><Td><Badge>{s.processing_status}</Badge></Td>
          <Td>{s.answer_count}</Td><Td>{s.flagged_count || ""}</Td><Td className="max-w-xs truncate text-xs text-slate-500">{s.processing_message}</Td>
          <Td>{!s.student_id ? <Button variant="secondary" onClick={() => setMapFor(s)}>Map student</Button> : s.processing_status !== "PROCESSING" && <Button variant="ghost" disabled={process.isPending} onClick={() => process.mutate(s.id)}>Re-process</Button>}</Td></tr>)}</Table>}
      {process.error && <div className="mt-3"><ErrorBox error={process.error} /></div>}</Card>
    {mapFor && <Modal title={`Map ${mapFor.original_filename}`} onClose={() => setMapFor(null)}>
      <Select value={pick} onChange={(e) => setPick(e.target.value)}><option value="">Select student…</option>{students.data?.map((s) => <option key={s.id} value={s.id}>{s.register_number} — {s.name}</option>)}</Select>
      {map.error && <div className="mt-2"><ErrorBox error={map.error} /></div>}
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={() => setMapFor(null)}>Cancel</Button>
        <Button disabled={!pick || map.isPending} onClick={() => map.mutate({ id: mapFor.id, student_id: pick }, { onSuccess: () => { api(`/api/answer-sheets/${mapFor.id}/process`, { method: "POST" }).then(() => qc.invalidateQueries({ queryKey: ["sheets"] })); } })}>Map & process</Button></div></Modal>}
  </div>;
}

export function Segmentation() {
  const qc = useQueryClient();
  const [examId, setExamId] = useState("");
  const [sheetId, setSheetId] = useState("");
  const [variant, setVariant] = useState<"original" | "processed" | "debug">("debug");
  const [pageIdx, setPageIdx] = useState(0);
  const [manual, setManual] = useState<any | null>(null);
  const [confirmRe, setConfirmRe] = useState<any | null>(null);
  const sheets = useQuery({ queryKey: ["sheets", examId], queryFn: () => api<any[]>(`/api/answer-sheets${examId ? `?exam_id=${examId}` : ""}`) });
  const seg = useQuery({ queryKey: ["segments", sheetId], queryFn: () => api<any>(`/api/answer-sheets/${sheetId}/segments`), enabled: !!sheetId,
    refetchInterval: (q) => (q.state.data?.processing_status === "PROCESSING" ? 2500 : false) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["segments", sheetId] }); qc.invalidateQueries({ queryKey: ["sheets"] }); };
  const approve = useMutation({ mutationFn: (id: string) => api(`/api/answers/${id}/approve`, { method: "POST" }), onSuccess: refresh });
  const flag = useMutation({ mutationFn: (id: string) => api(`/api/answers/${id}/needs-correction`, { method: "POST" }), onSuccess: refresh });
  const approveAll = useMutation({ mutationFn: (inc: boolean) => api(`/api/answer-sheets/${sheetId}/approve-all`, { body: { include_flagged: inc } }), onSuccess: refresh });
  const reprocess = useMutation({ mutationFn: () => api(`/api/answer-sheets/${sheetId}/process`, { method: "POST" }), onSuccess: () => { setConfirmRe(null); refresh(); } });
  const s = seg.data;
  const page = s?.pages?.[pageIdx];
  const det = page?.detection;
  return <div><PageTitle title="Segmentation review" sub="Inspect detected question markers, crop boundaries, OCR and confidence. Only approved answers can be assigned." />
    <Card><div className="grid gap-3 md:grid-cols-2"><Field label="Examination"><ExamPicker value={examId} onChange={(v) => { setExamId(v); setSheetId(""); }} /></Field>
      <Field label="Answer sheet"><Select value={sheetId} onChange={(e) => { setSheetId(e.target.value); setPageIdx(0); }}><option value="">Select sheet…</option>
        {sheets.data?.map((x) => <option key={x.id} value={x.id}>{x.register_number || "unmapped"} — {x.original_filename} ({x.processing_status})</option>)}</Select></Field></div></Card>
    {!sheetId ? <div className="mt-6"><Empty title="Choose an answer sheet to review" /></div> : seg.isLoading ? <div className="mt-6"><Spinner /></div> : seg.error ? <div className="mt-6"><ErrorBox error={seg.error} /></div> : <>
      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <Card title={<span>Page viewer <Badge>{s.processing_status}</Badge></span>} actions={<>
          {(["original", "processed", "debug"] as const).map((v) => <Button key={v} variant={variant === v ? "primary" : "secondary"} onClick={() => setVariant(v)}>{v}</Button>)}</>}>
          {s.processing_status === "PROCESSING" ? <Spinner label="Processing (OCR + segmentation)…" /> : <>
            {s.pages.length > 1 && <div className="mb-2 flex gap-1">{s.pages.map((p: any, i: number) => <Button key={p.id} variant={i === pageIdx ? "primary" : "secondary"} onClick={() => setPageIdx(i)}>Page {p.page_number}</Button>)}</div>}
            {page && <ImageViewer key={`${page.id}-${variant}`} src={`/api/answer-pages/${page.id}/image?variant=${variant}`} height="60vh" alt={`Page ${page.page_number} (${variant})`} />}
            {variant === "debug" && <p className="mt-2 text-xs text-slate-500">Red = detected markers · green = crop boundaries · orange = rejected candidates. Deskew angle {page?.deskew_angle ?? 0}°.</p>}
            {det && <div className="mt-3 text-xs text-slate-600"><p><b>Detected markers:</b> {det.markers.map((m: any) => `Q${m.question_number} (${Math.round(m.confidence * 100)}%, y=${m.y})`).join(", ") || "none"}</p>
              {det.rejected?.length > 0 && <p className="mt-1"><b>Rejected:</b> {det.rejected.map((r: any) => `“${r.text}” – ${r.reason}`).join("; ")}</p>}</div>}</>}
          {s.processing_message && <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">{s.processing_message}</p>}</Card>
        <Card title="Segmented answers" actions={<><Button variant="secondary" onClick={() => approveAll.mutate(false)} disabled={approveAll.isPending}>Approve all</Button><Button variant="ghost" onClick={() => setConfirmRe(true)}>Re-run processing</Button></>}>
          {approveAll.data && <p className="mb-2 text-xs text-slate-500">Approved {approveAll.data.approved}, skipped {approveAll.data.skipped} (flagged answers need individual approval).</p>}
          {(approve.error || flag.error || reprocess.error) && <ErrorBox error={approve.error || flag.error || reprocess.error} />}
          <div className="space-y-4">{s.answers.map((a: any) => <div key={a.id} className="rounded-lg border p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2"><b>Q{a.question_number}</b><Badge>{a.segmentation_status}</Badge>{a.segmentation_label && <Badge>{a.segmentation_label}</Badge>}
              <span className="text-xs text-slate-500">seg {a.segmentation_confidence != null ? Math.round(a.segmentation_confidence * 100) : 0}% · OCR <Badge>{a.ocr_status}</Badge> {a.ocr_confidence ?? ""}</span></div>
            {a.has_image ? <ImageViewer src={`/api/answers/${a.id}/image`} height="160px" alt={`Q${a.question_number} crop`} /> : <p className="rounded bg-red-50 p-3 text-sm text-red-700">{a.meta?.reason || "No crop"} — use manual correction.</p>}
            {a.extracted_text && <p className="mt-2 line-clamp-3 text-xs text-slate-600">{a.extracted_text}</p>}
            <div className="mt-2 flex flex-wrap gap-2"><Button disabled={!a.has_image || a.segmentation_status === "READY_FOR_EVALUATION" || approve.isPending} onClick={() => approve.mutate(a.id)}>Approve</Button>
              <Button variant="secondary" onClick={() => flag.mutate(a.id)}>Mark for correction</Button><Button variant="secondary" onClick={() => setManual(a)}>Correct manually</Button></div></div>)}</div></Card></div>
      {manual && <ManualModal answer={manual} sheet={s} onClose={() => setManual(null)} onDone={() => { setManual(null); refresh(); }} />}
      {confirmRe && <Confirm message="Re-run automatic segmentation for this sheet? Existing crops are replaced (blocked if any answer is already assigned or evaluated)." onCancel={() => setConfirmRe(null)} onConfirm={() => reprocess.mutate()} />}</>}
  </div>;
}

function ManualModal({ answer, sheet, onClose, onDone }: { answer: any; sheet: any; onClose: () => void; onDone: () => void }) {
  const [pageNo, setPageNo] = useState(1);
  const [y0, setY0] = useState("0");
  const [y1, setY1] = useState("400");
  const pg = sheet.pages.find((p: any) => p.page_number === pageNo);
  const m = useMutation({ mutationFn: () => api(`/api/answers/${answer.id}/segmentation`, { method: "PUT", body: { regions: [{ page_number: pageNo, y_start: Number(y0), y_end: Number(y1) }] } }), onSuccess: onDone });
  return <Modal title={`Manual crop – Q${answer.question_number}`} onClose={onClose}>
    <p className="mb-3 text-xs text-slate-500">Enter vertical boundaries in processed-page pixels (page height {pg?.height}). Use the debug view to read marker positions. The crop is re-OCR’d and must be approved afterwards.</p>
    <div className="grid grid-cols-3 gap-3"><Field label="Page"><Select value={pageNo} onChange={(e) => setPageNo(Number(e.target.value))}>{sheet.pages.map((p: any) => <option key={p.id} value={p.page_number}>{p.page_number}</option>)}</Select></Field>
      <Field label="Top (y)"><Input type="number" value={y0} onChange={(e) => setY0(e.target.value)} /></Field><Field label="Bottom (y)"><Input type="number" value={y1} onChange={(e) => setY1(e.target.value)} /></Field></div>
    {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={m.isPending} onClick={() => m.mutate()}>Apply crop</Button></div></Modal>;
}

export function Assignments() {
  const qc = useQueryClient();
  const [examId, setExamId] = useState("");
  const [facultyId, setFacultyId] = useState("");
  const [qn, setQn] = useState("");
  const [reassign, setReassign] = useState<any | null>(null);
  const [target, setTarget] = useState("");
  const params = new URLSearchParams({ ...(examId && { exam_id: examId }), ...(facultyId && { faculty_id: facultyId }), ...(qn && { question_number: qn }) });
  const list = useQuery({ queryKey: ["assignments", params.toString()], queryFn: () => api<any[]>(`/api/assignments?${params}`) });
  const wl = useQuery({ queryKey: ["workload", examId], queryFn: () => api<any[]>(`/api/assignments/workload${examId ? `?exam_id=${examId}` : ""}`) });
  const un = useQuery({ queryKey: ["unassigned", examId], queryFn: () => api<any[]>(`/api/assignments/unassigned?exam_id=${examId}`), enabled: !!examId });
  const faculty = useQuery({ queryKey: ["faculty"], queryFn: () => api<any[]>("/api/faculty") });
  const refresh = () => ["assignments", "workload", "unassigned", "faculty"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const auto = useMutation({ mutationFn: () => api("/api/assignments/auto-assign", { body: { exam_id: examId } }), onSuccess: refresh });
  const re = useMutation({ mutationFn: () => api(`/api/assignments/${reassign.id}/reassign`, { body: { faculty_id: target || null } }), onSuccess: () => { setReassign(null); setTarget(""); refresh(); } });
  return <div><PageTitle title="Question-level assignments" sub="Each answer (not the whole paper) is assigned to an eligible, available faculty member with spare capacity." />
    <Card><div className="flex flex-wrap items-end gap-3"><div className="w-72"><Field label="Examination"><ExamPicker value={examId} onChange={setExamId} /></Field></div>
      <Button disabled={!examId || auto.isPending} onClick={() => auto.mutate()}>{auto.isPending ? "Assigning…" : "Run automatic assignment"}</Button></div>
      {auto.error && <div className="mt-3"><ErrorBox error={auto.error} /></div>}
      {auto.data && <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm"><p>Assigned <b>{auto.data.assigned}</b> answers; <b>{auto.data.unassigned.length}</b> could not be assigned{auto.data.message ? ` (${auto.data.message})` : ""}.</p>
        {auto.data.unassigned.slice(0, 5).map((u: any) => <p key={u.answer_id} className="text-xs text-amber-700">• {u.reason}</p>)}
        {auto.data.skipped_faculty.map((f: any, i: number) => <p key={i} className="text-xs text-slate-500">• {f.faculty}: {f.reason}</p>)}</div>}</Card>
    <div className="mt-6 grid gap-5 lg:grid-cols-3"><Card title="Faculty workload">{wl.isLoading ? <Spinner /> : <Table head={["Faculty", "Active", "Done", "Capacity"]}>{wl.data?.map((w) => <tr key={w.faculty_id}><Td>{w.name}</Td><Td>{w.active}</Td><Td>{w.completed}</Td><Td>{w.capacity ?? "–"}{w.available === false && " (unavailable)"}</Td></tr>)}</Table>}</Card>
      <Card className="lg:col-span-2" title={`Not assigned${examId ? ` (${un.data?.length ?? 0})` : ""}`}>{!examId ? <p className="text-sm text-slate-500">Select an examination.</p> : !un.data?.length ? <p className="text-sm text-slate-500">Everything is assigned.</p> :
        <Table head={["Student", "Q", "Reason"]}>{un.data.map((u) => <tr key={u.answer_id}><Td>{u.register_number}</Td><Td>Q{u.question_number}</Td><Td className="text-xs">{u.reason}</Td></tr>)}</Table>}</Card></div>
    <Card className="mt-6" title="Assignments" actions={<><Select aria-label="Faculty filter" value={facultyId} onChange={(e) => setFacultyId(e.target.value)}><option value="">All faculty</option>{faculty.data?.map((f) => <option key={f.id} value={f.id}>{f.full_name}</option>)}</Select>
      <Input aria-label="Question filter" className="w-24" placeholder="Q #" value={qn} onChange={(e) => setQn(e.target.value)} /></>}>
      {list.isLoading ? <Spinner /> : list.error ? <ErrorBox error={list.error} /> : !list.data?.length ? <Empty title="No assignments yet" /> :
        <Table head={["Student", "Q", "Faculty", "Status", "Assigned", ""]}>{list.data.map((a) => <tr key={a.id}><Td>{a.register_number}</Td><Td>Q{a.question_number}</Td><Td>{a.faculty_name}</Td><Td><Badge>{a.status}</Badge></Td>
          <Td>{new Date(a.assigned_at).toLocaleString()}</Td><Td>{(a.status === "ASSIGNED" || a.status === "IN_PROGRESS") && <Button variant="ghost" onClick={() => setReassign(a)}>Reassign</Button>}</Td></tr>)}</Table>}</Card>
    {reassign && <Modal title={`Reassign Q${reassign.question_number} (${reassign.register_number})`} onClose={() => setReassign(null)}>
      <Select value={target} onChange={(e) => setTarget(e.target.value)}><option value="">Automatic (lowest workload)</option>{faculty.data?.filter((f) => f.id !== reassign.faculty_id).map((f) => <option key={f.id} value={f.id}>{f.full_name} ({f.current_assignment_count}/{f.max_active_assignments})</option>)}</Select>
      {re.error && <div className="mt-2"><ErrorBox error={re.error} /></div>}
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={() => setReassign(null)}>Cancel</Button><Button disabled={re.isPending} onClick={() => re.mutate()}>Reassign</Button></div></Modal>}
  </div>;
}
