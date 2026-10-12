import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "../lib/api";

export type Role = "ADMIN" | "FACULTY" | "REVIEWER";
export interface User { id: string; full_name: string; email: string; role: Role }
interface Ctx { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<User>; logout: () => void }

const AuthCtx = createContext<Ctx>(null as any);
export const useAuth = () => useContext(AuthCtx);
export const homeFor = (role: Role) => (role === "ADMIN" ? "/admin/dashboard" : role === "FACULTY" ? "/faculty/dashboard" : "/reviewer/dashboard");

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  useEffect(() => {
    if (!getToken()) return;
    api<User>("/api/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);
  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ access_token: string; user: User }>("/api/auth/login", { body: { email, password } });
    setToken(r.access_token); setUser(r.user); return r.user;
  }, []);
  const logout = useCallback(() => { setToken(null); setUser(null); }, []);
  return <AuthCtx.Provider value={{ user, loading, login, logout }}>{children}</AuthCtx.Provider>;
}
