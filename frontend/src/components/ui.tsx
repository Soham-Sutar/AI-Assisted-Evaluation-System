import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes, forwardRef } from "react";
import { AlertCircle, Inbox, Loader2, X } from "lucide-react";

const cx = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(" ");

export function Button({ variant = "primary", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  const styles = { primary: "bg-brand-500 text-white hover:bg-brand-600", secondary: "bg-white border border-slate-300 text-slate-700 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-700", ghost: "text-slate-600 hover:bg-slate-100" }[variant];
  return <button {...p} className={cx("inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500", styles, className)} />;
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) =>
  <input ref={ref} {...p} className={cx("w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500", className)} />);
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) =>
  <textarea ref={ref} {...p} className={cx("w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500", className)} />);
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...p }, ref) =>
  <select ref={ref} {...p} className={cx("w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none", className)} />);

export function Field({ label, error, children, hint }: { label: string; error?: string; children: ReactNode; hint?: string }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium text-slate-700">{label}</span>{children}
    {hint && !error && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    {error && <span role="alert" className="mt-1 block text-xs text-red-600">{error}</span>}</label>;
}

export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={cx("rounded-lg border border-slate-200 bg-white shadow-sm", className)}>
    {(title || actions) && <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3"><h2 className="font-semibold text-slate-800">{title}</h2><div className="flex gap-2">{actions}</div></header>}
    <div className="p-4">{children}</div></section>;
}

const TONES: Record<string, string> = {
  green: "bg-emerald-100 text-emerald-800", yellow: "bg-amber-100 text-amber-800", red: "bg-red-100 text-red-800",
  blue: "bg-blue-100 text-blue-800", gray: "bg-slate-100 text-slate-700", purple: "bg-violet-100 text-violet-800" };
const STATUS_TONE: Record<string, string> = {
  PROCESSED: "green", READY_FOR_EVALUATION: "green", COMPLETED: "green", COMPLETE: "green", RESOLVED: "green", OK: "green", High: "green",
  NEEDS_REVIEW: "yellow", NEEDS_CORRECTION: "red", FAILED: "red", ESCALATED: "red", LOW_CONFIDENCE: "yellow", Medium: "yellow", Low: "red", HIGH: "red",
  MEDIUM: "yellow", LOW: "gray", PROCESSING: "blue", ASSIGNED: "blue", IN_PROGRESS: "blue", OPEN: "yellow", DETECTED: "blue", PENDING_REVIEW: "yellow",
  INCOMPLETE: "gray", UPLOADED: "gray", BLANK: "gray", REVIEWER: "purple", FACULTY: "blue", ADMIN: "purple" };
export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const t = tone || STATUS_TONE[String(children)] || "gray";
  return <span className={cx("inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", TONES[t])}>{String(children).replaceAll("_", " ")}</span>;
}

export const Spinner = ({ label = "Loading…" }: { label?: string }) => <div role="status" className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>;
export const ErrorBox = ({ error }: { error: unknown }) => <div role="alert" className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{(error as Error)?.message || "Something went wrong"}</div>;
export const Empty = ({ title, hint }: { title: string; hint?: string }) => <div className="flex flex-col items-center gap-1 py-10 text-center text-slate-500"><Inbox className="h-8 w-8" /><p className="font-medium">{title}</p>{hint && <p className="text-sm">{hint}</p>}</div>;

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
    <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-lg bg-white p-5 shadow-xl">
      <div className="mb-3 flex items-center justify-between"><h3 className="text-lg font-semibold">{title}</h3><button aria-label="Close" onClick={onClose}><X className="h-5 w-5" /></button></div>{children}</div></div>;
}

export function Confirm({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return <Modal title="Please confirm" onClose={onCancel}><p className="mb-4 text-sm text-slate-600">{message}</p>
    <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onCancel}>Cancel</Button><Button variant="danger" onClick={onConfirm}>Confirm</Button></div></Modal>;
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b bg-slate-50 text-xs uppercase text-slate-500"><tr>{head.map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{children}</tbody></table></div>;
}
export const Td = ({ children, className }: { children?: ReactNode; className?: string }) => <td className={cx("px-3 py-2 align-middle", className)}>{children}</td>;
export const PageTitle = ({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) =>
  <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold text-slate-900">{title}</h1>{sub && <p className="text-sm text-slate-500">{sub}</p>}</div><div className="flex gap-2">{actions}</div></div>;
export const Stat = ({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) =>
  <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p>{sub && <p className="text-xs text-slate-500">{sub}</p>}</div>;
