import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Navigate, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth/AuthContext";
import { Button, ErrorBox, Field, Input } from "../components/ui";

const schema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Password is required") });
type Form = z.infer<typeof schema>;

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<unknown>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) });
  if (user) return <Navigate to={homeFor(user.role)} replace />;
  const onSubmit = async (v: Form) => {
    setError(null);
    try { const u = await login(v.email, v.password); nav(homeFor(u.role), { replace: true }); } catch (e) { setError(e); }
  };
  return <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 to-brand-700 p-4">
    <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm space-y-4 rounded-xl bg-white p-8 shadow-2xl" aria-label="Sign in">
      <div><h1 className="text-2xl font-bold">EvalAI</h1><p className="text-sm text-slate-500">Modular Examination Evaluation Platform</p></div>
      {!!error && <ErrorBox error={error} />}
      <Field label="Email" error={errors.email?.message}><Input type="email" autoComplete="username" {...register("email")} /></Field>
      <Field label="Password" error={errors.password?.message}><Input type="password" autoComplete="current-password" {...register("password")} /></Field>
      <Button type="submit" className="w-full" disabled={isSubmitting}>{isSubmitting ? "Signing in…" : "Sign in"}</Button>
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-xs text-slate-600 space-y-1">
        <p className="font-semibold text-slate-700">Development Accounts</p>
        <p className="text-slate-500 text-[11px]">
          Configured in <code className="bg-slate-200 px-1 py-0.5 rounded text-slate-800">.env</code> (details in README):
        </p>
        <ul className="list-disc list-inside text-[11px] text-slate-600 space-y-0.5 font-mono">
          <li>admin@example.com (Admin)</li>
          <li>faculty1@example.com (Faculty)</li>
          <li>reviewer@example.com (Reviewer)</li>
        </ul>
      </div>
    </form></div>;
}
