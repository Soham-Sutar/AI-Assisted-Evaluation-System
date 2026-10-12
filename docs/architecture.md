# Architecture
Browser → React SPA → FastAPI (`/api/*`, JWT) → PostgreSQL (SQLAlchemy 2, Alembic) + `storage/{original,processed,segmented,model_answers,exports,debug}`.

Layers: `api/` (thin routers; object-level authorization in `api/deps.py`) → `services/` (business logic) → `cv/`, `ai/` (replaceable engines).
* OCR: `services/ocr_service.py` `OCRProvider.extract(image) -> OCRResult` (Tesseract). Failure => `status=FAILED`, never fabricated text.
* Embeddings: `ai/embeddings.py` `EmbeddingProvider.similarity(a,b)`; MiniLM or TF-IDF fallback; model loaded once.
* Storage: `services/storage_service.py` (`LocalStorage`; server-generated uuid names; `resolve()` blocks path traversal).
* Background: FastAPI `BackgroundTasks` (sheet processing, AI evaluation); each task owns its DB session.

Security: bcrypt; JWT; role read from the DB (token role claim ignored — tested with a forged token); faculty see only their own assignments (404, not 403,
for others); reviewers only answers with a review case; AI score hidden from faculty until their own submission; anonymous candidate codes for faculty
(setting); uploads validated by extension + real decode/magic bytes + size cap; audit log never stores secrets.

Flow: upload → `answer_sheets/answer_pages` → `segmentation_service.process_answer_sheet` → `answers` (crop, OCR, confidence) → approve →
`assignment_service.auto_assign` → `evaluation_service` → `ai_evaluation_service` → `discrepancy_service.check_and_flag` → `review_service` → `result_service`.
