---
trigger: glob
---

# Backend Rule

Apply this rule when working on `backend/**`.

## Scope
FastAPI, Python, SQLAlchemy, Alembic, authentication, APIs, services, workers, validation, and backend tests.

## Requirements
- Read `AGENTS.md` first.
- Read only the relevant sections of `ARCHITECTURE.md` and `DEVELOPMENT_RULES.md`.
- Preserve the existing backend module structure.
- Use FastAPI routers, Pydantic schemas, SQLAlchemy models/services, and dependency-based authentication consistently.
- Enforce authorization on the backend; never rely on frontend role checks alone.
- Use hashed passwords and JWT/session mechanisms already defined by the project.
- Validate all request data and uploaded files.
- Never expose secrets, database credentials, or private storage paths to the frontend.
- Use clear, stable API error responses.
- Keep business logic out of route handlers when it belongs in services.
- Prefer small, testable service functions.
- Preserve auditability and evaluation provenance.
- AI failures must never prevent human faculty evaluation.
- Do not silently change API contracts or database semantics.

## Verification
Run targeted backend tests for the changed module and relevant API/authentication paths. Fix failures caused by the change before reporting completion.

## Output
Report changed files, verification commands/results, and any remaining issue. Do not implement the next task automatically.
