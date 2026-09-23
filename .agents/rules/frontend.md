---
trigger: glob
---

# Frontend Rule

Apply this rule when working on `frontend/**`.

## Scope
React, TypeScript, Vite, Tailwind CSS, shadcn/ui, routing, forms, TanStack Query, dashboards, image viewers, and frontend tests.

## Requirements
- Read `AGENTS.md` first.
- Read only relevant sections of `PROJECT_KNOWLEDGE.md`, `ARCHITECTURE.md`, and `DEVELOPMENT_RULES.md`.
- Use the existing component and page structure before creating new abstractions.
- Keep UI professional, academic, clean, readable, responsive, and accessible.
- Prefer reusable components and consistent loading/error/empty states.
- Use typed API data and existing query/mutation patterns.
- Enforce role-aware navigation in the UI, but remember backend authorization is authoritative.
- Faculty evaluation must allow independent human submission before showing AI comparison data.
- Do not fabricate segmentation, assignment, AI scores, review outcomes, or final results.
- Preserve original answer-image display and evaluation context.
- Validate marks and comments before submission.
- Avoid unnecessary animations, gradients, decorative graphics, or duplicate components.

## Verification
Run targeted type-check, lint, unit/component tests, and the affected user flow when practical. Do not run unrelated exhaustive checks unless needed.

## Output
Report changed files and focused verification results. Do not implement the next task automatically.
