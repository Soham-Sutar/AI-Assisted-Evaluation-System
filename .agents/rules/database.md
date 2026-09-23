---
trigger: model_decision
---

# Database Rule

Apply this rule when working on PostgreSQL, SQLAlchemy models, Alembic migrations, repositories, or persistence logic.

## Requirements
- Read `AGENTS.md` first.
- Read relevant sections of `ARCHITECTURE.md` and `DEVELOPMENT_RULES.md`.
- PostgreSQL is the primary database; do not introduce SQLite as the primary implementation.
- Preserve the documented entities and relationships unless the specification requires a change.
- Use migrations for schema changes.
- Add appropriate foreign keys, uniqueness constraints, indexes, and nullability.
- Preserve evaluation history and provenance.
- Do not overwrite historical faculty/AI/reviewer evaluation records when a new evaluation event should be recorded.
- Final score semantics must remain:
  - normal answer -> faculty marks
  - reviewed answer -> reviewer marks
  - AI marks never automatically replace faculty/reviewer marks
- Avoid destructive migrations unless explicitly required.
- Never store plaintext passwords or secrets.
- Use transactions for multi-record operations where consistency matters.

## Verification
Run the relevant migration checks and database/API tests. Verify schema changes against existing workflows before completion.

## Output
Report schema changes, migration status, and verification results. Do not implement unrelated database work.
