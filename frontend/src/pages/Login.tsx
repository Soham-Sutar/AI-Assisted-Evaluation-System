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
      <p className="text-center text-xs text-slate-400">Development accounts are listed in the README.</p>
    </form></div>;
}
