# Bug Fix Workflow

Description: Diagnose and fix one reproducible EvalAI bug with minimal scope.

## Steps
1. Read `AGENTS.md`.
2. Reproduce or inspect the reported failure.
3. Identify the root cause before editing.
4. Read only the documentation relevant to the affected subsystem.
5. Implement the smallest correct fix.
6. Add or update a focused regression test.
7. Run the regression test and related targeted checks.
8. Verify that authentication, authorization, persistence, and error handling remain correct when relevant.
9. Report root cause, changed files, verification results, and any remaining risk.

## Guardrails
- Do not rewrite unrelated modules.
- Do not hide errors with broad exception handling.
- Do not change documented behavior merely to make a test pass.
- Do not implement the next feature after the bug is fixed.
