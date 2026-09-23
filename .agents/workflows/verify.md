# Verification Workflow

Description: Verify the current implementation without adding new features.

## Steps
1. Read `AGENTS.md`.
2. Inspect the changed files and git diff/status.
3. Identify the smallest relevant verification set.
4. Run focused backend/frontend/database/image-processing tests as applicable.
5. Run build/type/lint checks only where relevant.
6. If a failure is caused by the current implementation, fix it and rerun the focused check.
7. Do not silently modify unrelated code.
8. Report:
   - checks executed
   - pass/fail results
   - remaining failures
   - files changed during verification
   - recommended next task

## Guardrails
- Verification is not permission to implement new features.
- Do not claim tests passed if they were not actually run.
