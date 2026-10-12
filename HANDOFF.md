# HANDOFF — state at end of session 2 (deadline: 7 Oct 2026)

## Done and verified (sandbox)
* Backend: 17-table PostgreSQL schema + Alembic 0001; auth/RBAC/IDOR; exams/questions/model answers/rubrics; students (+CSV); faculty & eligibility/availability;
  upload (validated) → OpenCV preprocessing/deskew → Tesseract → marker detection → crops/multi-page merge → OCR/confidence → segmentation review API + manual crop;
  question-level auto-assignment/reassign; faculty draft/submit; independent AI scorer; discrepancy → review cases; reviewer resolve/escalate; results/CSV; analytics; audit; settings.
  **74 API operations; 48 pytest tests pass** (`cd backend && pytest`, ~3.5 min, needs local PostgreSQL with db `evalai_test`; helper `/home/claude/pgup.sh` was sandbox-only).
* Frontend: all routes from GUIDE.md implemented (admin/faculty/reviewer). **15 vitest tests pass, `tsc` clean, `vite build` OK.**
* Live smoke test over real HTTP (uvicorn): upload → async processing → 3 segmented answers (High confidence) → OK.
* Docs: README.md, docs/{architecture,segmentation,ai-evaluation,database,api}.md.

## NOT done / NOT verified — do these next, in order
1. **`docker compose up -d --build` has never been run** (no Docker in sandbox). Build it, fix whatever breaks (likely: torch CPU wheel step, tesseract/opencv libs, nginx proxy).
   Confirm `SEED_ON_START` seeding and that `./demo_sheets` appears on the host.
2. **Click through the UI in a real browser** with the full demo journey (README). Only jsdom tests + type-check/build exist; layout/UX bugs are likely. Check: upload progress,
   segmentation page viewer, faculty evaluate page, reviewer detail, Results "R" markers, charts render.
3. **MiniLM path untested** (HF unreachable in sandbox). With internet: `AI_PROVIDER=sentence-transformers`, run the E2E, then re-check calibration constants in
   `backend/app/ai/embeddings.py` (`sem_lo/sem_hi/pt_lo/pt_hi`) against graded sample answers (see /tmp-style script in docs/ai-evaluation.md).
4. **Real handwriting**: test with 2–3 real scanned sheets; expect low OCR confidence. Tune `seg_marker_min_conf`, blob re-read, `ocr_low_confidence` in `core/config.py`.
   Known observed weakness: a jittered `Q1` was read as `QO]` (conf 25) and rejected → answer flagged for manual crop (by design).
5. **PDF upload** with a genuine multi-page PDF (only the invalid-PDF rejection path is tested).
6. Segmentation review UX gaps vs GUIDE §21: drag-to-adjust boundaries, split, merge, change question number (manual numeric crop exists).
7. Missing tests: students CSV import, settings endpoints/runtime threshold change, reviewer conflict-of-interest, escalate, frontend review form, a11y checks.
8. Reliability: sheets left in PROCESSING after a server restart (add startup sweep to mark them FAILED); login rate limiting.
9. P1 leftovers: PDF export of results; notifications.

## Gotchas learned
* Sandbox `/bin/sh` is dash: **no brace expansion** (`mkdir -p a/{b,c}` creates a literal dir) — use `bash -c`.
* Never `pkill -f "<pattern>"` where the pattern appears in your own command line.
* FastAPI 0.142 registers routers as `_IncludedRouter`; count routes via `app.openapi()["paths"]`.
* Background tasks run synchronously inside `TestClient`, so API tests see AI results immediately.
