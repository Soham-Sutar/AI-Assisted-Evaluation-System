# API
Interactive docs: `/docs` (Swagger), `/redoc`. 74 operations. Groups: auth, subjects, exams, questions (+model-answer), students (+CSV import), faculty (+`/me/*`),
answer-sheets (upload/process/segments/approve-all/manual), answers (image, OCR text, approve, segmentation, ai-evaluate, evaluation), assignments
(auto-assign, list, unassigned, workload, reassign), evaluations (create/update/history), reviews (list/detail/assign/resolve/escalate),
exams/{id}/results (+calculate, export.csv), analytics, audit-logs, settings.
Errors: 401 unauthenticated · 403 wrong role · 404 for objects the caller may not access (no existence leak) · 409 state conflict · 422 validation.
