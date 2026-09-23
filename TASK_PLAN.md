# TASK_PLAN.md

## Purpose

This file is the development roadmap and verification view derived from the original guide. The source guide specifies the required implementation order and acceptance criteria, but it does **not** record actual completed/in-progress/pending implementation status. Therefore, no task is marked complete merely because it is described in the guide.

## Current project state from the source

**Documentation/specification state:** complete prototype requirements are specified.

**Implementation state:** not established by `GUIDE.md`. The source contains requirements, architecture, implementation order, tests, and acceptance criteria, but no reliable completion log. Treat implementation status as **Not verified** until the codebase is inspected.

### Status meanings

- **Not verified** — the source guide specifies the requirement, but does not prove implementation.
- **In progress** — use only after inspecting the codebase and confirming active implementation work.
- **Completed** — use only after implementation and verification satisfy the documented acceptance criteria.
- **Blocked** — use only when a concrete dependency or issue prevents progress.

## Roadmap

### Phase 1 — Infrastructure
- Docker
- PostgreSQL
- FastAPI
- React
- migrations
- authentication

**Verification:** Docker startup, database connectivity, migrations, seeded authentication, and role-protected routes.

### Phase 2 — Academic setup
- subjects
- examinations
- questions
- model answers
- rubrics
- students
- faculty and subject eligibility

**Verification:** Admin can create/configure the academic entities and retrieve them through real APIs.

### Phase 3 — Image processing
- answer-sheet uploads
- preprocessing
- OCR
- question detection
- segmentation
- persistent storage
- segmentation review
- manual fallback

**Verification:** Real uploaded images produce stored question-wise answer records and can be reviewed/corrected.

### Phase 4 — Assignment
- faculty availability
- maximum workload
- current workload
- subject eligibility
- question-wise distribution
- reassignment

**Verification:** Only eligible faculty receive assignments; workload balancing works; unassignable work remains visible.

### Phase 5 — Evaluation
- faculty queue and evaluation screen
- evaluation persistence/versioning
- independent AI evaluation
- AI explanation/confidence

**Verification:** Faculty can submit marks without seeing AI recommendations first; AI produces a separate stored reference evaluation.

### Phase 6 — Moderation
- discrepancy detection
- review queue
- reviewer assignment
- re-evaluation
- resolution/escalation

**Verification:** Configured discrepancy thresholds create review cases and reviewer decisions are persisted.

### Phase 7 — Results
- final-score aggregation
- results table
- student detail results
- CSV/PDF exports where practical
- evaluation history

**Verification:** Normal answers use faculty marks; reviewed answers use reviewer marks; totals and percentages are reproducible from stored data.

### Phase 8 — Analytics
- evaluation completion
- faculty workload
- AI vs faculty comparison
- discrepancy distribution
- faculty evaluation patterns
- question statistics

**Verification:** Analytics are derived from stored records and use neutral, non-diagnostic language.

### Phase 9 — Polish
- loading states
- empty states
- human-readable error states
- accessibility
- audit logs
- notifications
- demo seed data
- documentation
- troubleshooting

**Verification:** Core demo remains functional under error/loading/empty conditions and the README permits a fresh setup from zero.

## Current priorities

Because the source does not contain an implementation progress log, the next priority should be determined by inspecting the repository against the phase order above. Do not claim a phase is complete from documentation alone.

## Known source-defined risk areas

- Handwritten OCR can fail or be inaccurate.
- Question-marker detection can fail or misread numbers.
- Multi-page answers require continuation handling.
- Segmentation may require manual correction.
- AI evaluation is inherently imperfect and must expose confidence/limitations.
- Discrepancy statistics are indicators, not proof of intentional bias.
- Large image batches and AI inference should not block HTTP requests.
- Uploaded files and student marks require strong authorization and auditability.

## Verification checklist

Use the complete acceptance criteria below as the authoritative verification checklist. Mark items only after testing the actual application.

# 102. IMPLEMENTATION ORDER

Build in this order:

### Phase 1

Infrastructure:

- Docker
- PostgreSQL
- FastAPI
- React
- migrations
- authentication

### Phase 2

Academic setup:

- subjects
- exams
- questions
- model answers
- students
- faculty

### Phase 3

Image processing:

- uploads
- preprocessing
- OCR
- question detection
- segmentation
- storage
- segmentation review

### Phase 4

Assignment:

- faculty availability
- workload
- question-wise distribution

### Phase 5

Evaluation:

- faculty UI
- evaluation storage
- AI scoring

### Phase 6

Moderation:

- discrepancy detection
- review queue
- re-evaluation

### Phase 7

Results:

- final score aggregation
- results table
- exports

### Phase 8

Analytics:

- workload
- discrepancy
- score distribution
- question statistics

### Phase 9

Polish:

- loading states
- error handling
- accessibility
- audit logs
- demo seed data
- documentation

---

---

# 83. ACCEPTANCE CRITERIA

The prototype is considered successful when:

### Authentication

- users can log in;
- role-based dashboards work.

### Exam setup

- admin can create subject/exam/questions;
- model answers can be stored.

### Upload

- admin can upload handwritten answer sheets.

### Segmentation

- uploaded sheets are processed;
- question markers are detected;
- answer regions are cropped;
- segmented images are saved;
- segmentation metadata is stored;
- admin can inspect segments.

### Faculty

- faculty sees only eligible assignments;
- faculty can view answer images;
- faculty can enter marks;
- submitted evaluations are stored.

### AI

- system extracts OCR text;
- AI compares answer with model answer;
- AI returns score/confidence/explanation.

### Discrepancy

- human vs AI scores are compared;
- significant discrepancies generate review cases.

### Review

- reviewer can re-evaluate;
- review result is recorded.

### Final result

- all question marks are aggregated;
- final marks are displayed;
- results can be exported.

---

---

# 104. DEFINITION OF DONE

The project is DONE only when a user can perform the following complete journey:

    1. Start application using Docker.

    2. Login as admin.

    3. Create/select an examination.

    4. Configure subject and questions.

    5. Add model answers and marking schemes.

    6. Add students.

    7. Add faculty and subject eligibility.

    8. Upload handwritten answer-sheet images.

    9. Process the images.

    10. See automatic question detection.

    11. See question-wise cropped images.

    12. Correct segmentation if necessary.

    13. Approve segmentation.

    14. Run automatic faculty assignment.

    15. Login as Faculty A.

    16. Faculty A sees only their assigned question answers.

    17. Faculty opens an answer image.

    18. Faculty evaluates it.

    19. Faculty submits marks.

    20. AI evaluation is generated independently.

    21. Human and AI scores are compared.

    22. Significant discrepancy creates a review case.

    23. Reviewer logs in.

    24. Reviewer sees the flagged answer and all relevant scores.

    25. Reviewer submits a review score.

    26. Final score is calculated.

    27. Admin opens Results.

    28. Admin sees per-question marks and total marks.

    29. Admin opens Analytics.

    30. Admin can inspect evaluation history.

This complete journey must be demonstrated using actual database records and actual uploaded/processed images.

---

## Milestone rule

A milestone is complete only when its implementation works through real APIs, persistent database records, actual uploaded/processed images where applicable, appropriate authorization, error handling, and tests. Cosmetic UI completion alone is insufficient.
