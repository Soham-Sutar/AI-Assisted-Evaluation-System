import { z } from "zod";

/** Marks must satisfy 0 <= marks <= max. Empty input is allowed only for drafts. */
export function marksSchema(max: number) {
  return z.number({ required_error: "Marks are required to submit", invalid_type_error: "Enter a number" })
    .min(0, "Marks cannot be negative").max(max, `Marks cannot exceed ${max}`);
}

export function parseMarks(raw: string): number | null {
  if (raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isNaN(n) ? NaN : n;
}

/** Returns an error message or null. `submit` makes a value mandatory. */
export function validateMarks(raw: string, max: number, submit: boolean): string | null {
  const v = parseMarks(raw);
  if (v === null) return submit ? "Marks are required to submit" : null;
  const r = marksSchema(max).safeParse(v);
  return r.success ? null : r.error.issues[0].message;
}
