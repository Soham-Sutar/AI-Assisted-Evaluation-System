---
trigger: model_decision
---

# AI and Computer Vision Rule

Apply this rule when working on OCR, image processing, answer segmentation, embeddings, AI evaluation, discrepancy detection, or analytics derived from evaluation data.

## Requirements
- Read `AGENTS.md` first.
- Read relevant sections of `PROJECT_KNOWLEDGE.md` and `ARCHITECTURE.md`.
- Preserve original uploaded answer-sheet files.
- Use real OCR/segmentation/AI pipelines for implemented functionality; do not fake results.
- Store useful confidence and provenance metadata.
- Question detection must support the documented marker patterns and contextual checks.
- Segmentation must remain manually correctable when confidence is low.
- Do not silently discard low-confidence results.
- AI evaluation is advisory, not final authority.
- Faculty evaluation must be independent before AI results are revealed.
- Never automatically replace faculty marks with AI marks.
- Discrepancy indicators must not be described as proof of intentional faculty bias.
- Use neutral terminology such as evaluation discrepancy, deviation, or evaluation pattern.
- AI confidence is a prototype estimate unless a calibrated probability model is actually implemented.
- AI failure must degrade gracefully and never block human evaluation.
- Keep model name/configuration and scoring parameters observable where appropriate.
- For similarity/keypoint scoring, preserve configurable weights and normalization rather than hard-coding unexplained behavior.

## Verification
Use representative image fixtures and targeted tests for OCR, marker detection, segmentation, scoring, discrepancy thresholds, and failure paths.

## Output
Report pipeline behavior, confidence handling, tests, and known limitations. Do not claim scientific validation unless it exists.
