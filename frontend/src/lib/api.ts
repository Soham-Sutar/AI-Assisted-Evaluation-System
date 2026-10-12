import { useEffect, useState } from "react";

const TOKEN_KEY = "evalai_token";
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

function detailToMessage(d: any, fallback: string): string {
  if (!d) return fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => (e?.msg ? `${(e.loc || []).slice(1).join(".")}: ${e.msg}` : String(e))).join("; ");
  return fallback;
}

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  let res: Response;
  try { res = await fetch(path, { method: opts.method || (body ? "POST" : "GET"), headers, body }); }
  catch { throw new ApiError(0, "Cannot reach the server. Is the backend running?"); }
  if (res.status === 401 && token) { setToken(null); window.location.href = "/login"; }
  if (!res.ok) {
    let d: any = null;
    try { d = (await res.json()).detail; } catch { /* non-JSON error */ }
    throw new ApiError(res.status, detailToMessage(d, `Request failed (${res.status})`));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/** Images are protected by the JWT, so <img src> cannot be used directly: fetch as a blob with the token. */
export function useAuthImage(path: string | null | undefined) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let revoked: string | null = null, cancelled = false;
    setUrl(null); setError(null);
    if (!path) return;
    fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => { if (!r.ok) throw new Error(r.status === 404 ? "Image not available" : "Could not load image"); return r.blob(); })
      .then((b) => { if (cancelled) return; revoked = URL.createObjectURL(b); setUrl(revoked); })
      .catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; if (revoked) URL.revokeObjectURL(revoked); };
  }, [path]);
  return { url, error };
}

export async function downloadFile(path: string, filename: string) {
  const r = await fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!r.ok) throw new ApiError(r.status, "Download failed");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob()); a.download = filename; a.click(); URL.revokeObjectURL(a.href);
}
