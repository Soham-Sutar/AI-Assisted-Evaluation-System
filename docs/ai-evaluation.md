# AI evaluation (advisory, independent)
Runs only after the faculty evaluation is stored. `ai/scorer.evaluate_answer(student_text, model_answer, max_marks, rubric, …)` has no faculty-score parameter (tested).
1. Normalise OCR text (marker prefix stripped). < 3 words ⇒ `FAILED` (recorded; faculty unaffected; a `LOW_AI_CONFIDENCE` review case is created).
2. Semantic: cosine(student, model answer) calibrated to [0,1] by provider-specific lo/hi (MiniLM 0.20–0.80; TF-IDF 0.10–0.55).
3. Key-points: rubric points (weights = marks) else model-answer sentences; each compared with sentence/window chunks of the answer; calibrated; weighted.
4. `normalized = ws·semantic + wk·keypoint` (weights normalised; default 0.5/0.5, env-configurable); `ai_marks = round(normalized·max, 1)` clamped to [0,max].
5. Confidence (heuristic): 0.35 OCR quality + 0.25 signal agreement + 0.15 length adequacy + 0.25 provider reliability.
Stored: marks, confidence, semantic, key-point score, explanation JSON (per-point status, formula, limitations), `model_name` (provider actually used), timestamp.
Discrepancy: `|faculty − ai| ≥ threshold` (absolute / relative / either; DB-overridable) ⇒ ReviewCase; priority by ratio to max marks.
Sanity check on graded samples (TF-IDF, rubric): paraphrase 9.2, partial 5.8, wrong topic 0.0, off-topic 0.0, copy of model 9.6.
