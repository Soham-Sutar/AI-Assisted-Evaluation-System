import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { setToken } from "../lib/api";

const USERS: Record<string, any> = {
  admin: { id: "1", full_name: "Admin", email: "admin@example.com", role: "ADMIN" },
  faculty: { id: "2", full_name: "Fac One", email: "faculty1@example.com", role: "FACULTY" },
  reviewer: { id: "3", full_name: "Rev", email: "reviewer@example.com", role: "REVIEWER" },
};

function mockFetch(handlers: Record<string, any>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: any) => {
    const key = Object.keys(handlers).find((k) => String(url).startsWith(k));
    if (!key) return new Response(JSON.stringify({ detail: "not mocked " + url }), { status: 404 });
    const h = handlers[key];
    const body = typeof h === "function" ? h(url, init) : h;
    return new Response(JSON.stringify(body), { status: body?.__status || 200, headers: { "Content-Type": "application/json" } });
  }));
}

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("login & role routing", () => {
  it("redirects anonymous users to the login page", async () => {
    mockFetch({});
    renderAt("/admin/dashboard");
    expect(await screen.findByRole("form", { name: /sign in/i })).toBeInTheDocument();
  });

  it("validates the login form before calling the API", async () => {
    mockFetch({});
    renderAt("/login");
    await userEvent.click(await screen.findByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows the server error on bad credentials", async () => {
    mockFetch({ "/api/auth/login": { detail: "Invalid email or password", __status: 401 } });
    renderAt("/login");
    await userEvent.type(await screen.findByLabelText(/email/i), "a@b.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid email or password/i);
  });

  it.each([["faculty", "/faculty/dashboard"], ["reviewer", "/reviewer/dashboard"], ["admin", "/admin/dashboard"]])("routes %s to their own home after login", async (role, home) => {
    mockFetch({ "/api/auth/login": { access_token: "t", token_type: "bearer", user: USERS[role] }, "/api/faculty/me/summary": { pending: 0, in_progress: 0, completed: 0, progress_pct: 0 },
      "/api/faculty/me/assignments": [], "/api/reviews": [], "/api/analytics/overview": { faculty_workload: [] } });
    renderAt("/login");
    await userEvent.type(await screen.findByLabelText(/email/i), USERS[role].email);
    await userEvent.type(screen.getByLabelText(/password/i), "Password123!");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getByRole("navigation", { name: /main/i })).toBeInTheDocument());
    expect(screen.getAllByRole("link").some((a) => a.getAttribute("href") === home)).toBe(true);
  });

  it("bounces a faculty user away from admin routes", async () => {
    setToken("t");
    mockFetch({ "/api/auth/me": USERS.faculty, "/api/faculty/me/summary": { pending: 1, in_progress: 0, completed: 0, progress_pct: 0 }, "/api/faculty/me/assignments": [] });
    renderAt("/admin/results");
    await waitFor(() => expect(screen.getByText(/my dashboard/i)).toBeInTheDocument());
    expect(screen.queryByText(/^Results$/)).not.toBeInTheDocument();
  });
});

describe("faculty evaluation form", () => {
  const answer = (over: any = {}) => ({ id: "a1", question_number: 2, candidate_code: "C-ABC123", examination_name: "IA1", subject: "OS", max_marks: 10, question_text: "Explain deadlock prevention.",
    model_answer_text: "m", rubric: null, extracted_text: "some ocr", ocr_status: "OK", ocr_corrected: false, page_start: 1, page_end: 1, my_evaluation: null, ...over });

  function setup(a: any, extra: Record<string, any> = {}) {
    setToken("t");
    mockFetch({ "/api/auth/me": USERS.faculty, "/api/answers/a1/image": new Response(), "/api/answers/a1": a, ...extra });
    renderAt("/faculty/evaluate/a1");
  }

  it("blocks submission with out-of-range marks and never calls the API", async () => {
    setup(answer());
    const input = await screen.findByLabelText("Marks");
    await userEvent.type(input, "11");
    await userEvent.click(screen.getByRole("button", { name: /submit evaluation/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot exceed 10/i);
    expect((fetch as any).mock.calls.some((c: any[]) => String(c[0]).startsWith("/api/evaluations"))).toBe(false);
  });

  it("requires marks to submit but allows an empty draft", async () => {
    setup(answer(), { "/api/evaluations": { id: "e1", is_draft: true } });
    await userEvent.click(await screen.findByRole("button", { name: /submit evaluation/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/required/i);
    await userEvent.click(screen.getByRole("button", { name: /save draft/i }));
    await waitFor(() => expect((fetch as any).mock.calls.some((c: any[]) => String(c[0]).startsWith("/api/evaluations"))).toBe(true));
  });

  it("does not show the AI score before submission, and locks + reveals it after", async () => {
    setup(answer({ ai_evaluation: undefined }));
    await screen.findByLabelText("Marks");
    expect(screen.queryByText(/AI reference score:/i)).not.toBeInTheDocument();
    expect(screen.getByText(/revealed only after you submit/i)).toBeInTheDocument();
  });

  it("is read-only once submitted and shows the AI reference", async () => {
    vi.unstubAllGlobals();
    setup(answer({ my_evaluation: { id: "e1", is_draft: false, marks_awarded: 7, comments: "ok", submitted_at: new Date().toISOString() },
      ai_evaluation: { status: "COMPLETED", ai_marks: 6.5, confidence_score: 0.8, model_name: "tfidf" } }));
    const input = await screen.findByLabelText("Marks");
    expect(input).toBeDisabled();
    expect(screen.queryByRole("button", { name: /submit evaluation/i })).not.toBeInTheDocument();
    expect(await screen.findByText(/AI reference score:/i)).toBeInTheDocument();
  });
});
