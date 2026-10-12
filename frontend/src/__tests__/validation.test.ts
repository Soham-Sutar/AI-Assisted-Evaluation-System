import { describe, expect, it } from "vitest";
import { parseMarks, validateMarks } from "../lib/validation";

describe("marks validation (0 <= marks <= max)", () => {
  it("accepts boundaries and in-range values", () => {
    for (const v of ["0", "10", "7.5"]) expect(validateMarks(v, 10, true)).toBeNull();
  });
  it("rejects out-of-range values", () => {
    expect(validateMarks("-1", 10, true)).toMatch(/negative/);
    expect(validateMarks("10.5", 10, true)).toMatch(/exceed 10/);
    expect(validateMarks("99", 10, false)).toMatch(/exceed/);
  });
  it("requires a value to submit but not to save a draft", () => {
    expect(validateMarks("", 10, true)).toMatch(/required/);
    expect(validateMarks("", 10, false)).toBeNull();
  });
  it("rejects non-numeric input", () => {
    expect(Number.isNaN(parseMarks("abc"))).toBe(true);
    expect(validateMarks("abc", 10, true)).not.toBeNull();
  });
});
