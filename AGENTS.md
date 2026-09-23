# AGENTS.md

## Purpose

This is the primary instruction file for AI coding agents working on the EvalAI prototype. The project is an **AI-Based Modular Answer Sheet Evaluation System with Bias Detection**: a human-in-the-loop examination platform that turns handwritten answer-sheet images into question-wise answer units, distributes them to eligible faculty, obtains independent AI reference evaluations, detects potentially significant evaluation discrepancies, supports review/re-evaluation, and calculates final student marks.

The original `GUIDE.md` is the authoritative source from which this refactor was produced. Detailed requirements are intentionally kept in the companion files:

- `PROJECT_KNOWLEDGE.md` — product requirements, workflows, users, features, UI/UX, AI behavior, and project constraints.
- `ARCHITECTURE.md` — technical architecture, data model, APIs, processing pipeline, modules, storage, infrastructure, and configuration.
- `DEVELOPMENT_RULES.md` — engineering, security, testing, logging, performance, and implementation rules.
- `TASK_PLAN.md` — prescribed implementation phases, acceptance criteria, definition of done, and source-defined project-state notes.

## Non-negotiable objective

Build a genuinely working full-stack prototype, not a collection of mock screens. The critical demonstration is:

**handwritten image → real OCR/question detection → real cropped answer images → database → real faculty assignment → faculty login → real evaluation → AI reference score → discrepancy detection → review → final student marks**

If trade-offs are necessary, prioritize this workflow over cosmetic features.

## Agent behavior

1. Treat the requirements in the companion files as authoritative; do not invent requirements that contradict them.
2. Before changing a subsystem, read the focused documentation relevant to that subsystem.
3. Preserve existing working behavior unless the task explicitly requires a change.
4. Prefer modular, explainable implementations with clear service/module boundaries.
5. Use real API calls, database records, image processing, assignments, evaluations, and calculations. Never fake core behavior.
6. Keep AI/CV components replaceable and independently testable.
7. Preserve original answer-sheet images and all evaluation history.
8. Keep secrets in environment variables; never expose credentials or tokens.
9. Maintain role-based authorization on the backend; never trust frontend role values.
10. Fail gracefully and provide manual fallbacks where OCR/segmentation/AI can fail.
11. Keep the application runnable through the documented Docker workflow.
12. Update relevant documentation and tests when behavior or architecture changes.

## Source-of-truth hierarchy

1. `GUIDE.md` — original authoritative specification used to create this refactor.
2. The five refactored files — organized copies of that specification; do not intentionally contradict one another.
3. Actual code/database behavior — implementation evidence that must be reconciled with the documented requirements when work is performed.
4. New design choices — allowed only when the specification leaves an implementation detail open; document meaningful decisions rather than silently changing requirements.

When documentation and implementation disagree, do not silently choose one. Identify the discrepancy and preserve the documented requirement unless the task explicitly changes it.

## Critical product restrictions

- AI is advisory, not the final authority.
- Faculty evaluation must remain independent before the AI score is revealed; AI recommendations must not anchor the initial faculty score.
- Never claim that a discrepancy proves intentional faculty bias. Use neutral terms such as **Evaluation discrepancy detected**, **Potential evaluation inconsistency**, or **Evaluation Pattern**.
- Do not automatically replace faculty marks with AI marks.
- Reviewed answers use the reviewer score; normal answers use the faculty score.
- Never fake AI scores, segmentation, assignment, or final results.
- Never destroy original uploaded images.
- Failed/low-confidence OCR must remain visible as uncertain and allow manual correction.
- Low-confidence segmentation must be reviewable and manually correctable.
- Faculty may only receive eligible assignments.
- AI failure must never block human evaluation.
- Uploaded files require validation, secure generated storage paths, size limits, and path-traversal protection.
- Database credentials and secrets must never reach the frontend.

## Development workflow

Follow the implementation order in `TASK_PLAN.md`:

1. Infrastructure and authentication.
2. Academic setup.
3. Upload, CV/OCR, segmentation, and segmentation review.
4. Question-wise faculty assignment.
5. Faculty evaluation and independent AI scoring.
6. Discrepancy detection and review.
7. Final results and exports.
8. Analytics.
9. Reliability, accessibility, auditability, demo data, and documentation.

For each task: inspect the relevant architecture and rules, implement the smallest coherent change, test it, verify authorization/error states, and update documentation if the behavior changes.

## Definition of done

The project is not done until the complete end-to-end journey works with actual database records and actual uploaded/processed images:

1. Start with Docker.
2. Log in as admin.
3. Configure an examination, subject, questions, model answers/rubrics, students, and faculty eligibility.
4. Upload and process handwritten answer sheets.
5. Detect and review question-wise segmentation.
6. Auto-assign eligible faculty.
7. Faculty sees only assigned answers and submits marks.
8. AI independently evaluates answers.
9. Human and AI scores are compared.
10. Significant discrepancies create review cases.
11. A reviewer can inspect and submit a review score.
12. Final marks are calculated and shown in Results.
13. Analytics and evaluation history are inspectable.

Use `TASK_PLAN.md` for the complete acceptance criteria and source-defined roadmap.
