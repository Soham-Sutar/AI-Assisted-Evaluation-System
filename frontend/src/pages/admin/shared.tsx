import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Select } from "../../components/ui";

export const useExams = () => useQuery({ queryKey: ["exams"], queryFn: () => api<any[]>("/api/exams") });

export function ExamPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const q = useExams();
  return <Select aria-label="Examination" value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Select examination…</option>{q.data?.map((e) => <option key={e.id} value={e.id}>{e.name} — {e.subject_name}</option>)}</Select>;
}
