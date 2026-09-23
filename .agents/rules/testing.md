---
trigger: model_decision
---

# Testing Rule

Apply this rule when writing or modifying tests or when verifying a completed implementation.

## Requirements
- Read `AGENTS.md` first.
- Read only the relevant testing sections of `DEVELOPMENT_RULES.md` and the affected architecture/feature documentation.
- Prefer focused tests tied to the changed behavior.
- Backend coverage should include unit tests for core services and API tests for authentication, authorization, uploads, assignments, evaluations, reviews, and results where affected.
- Frontend coverage should include route protection, role behavior, forms, validation, and important evaluation workflows where affected.
- Image-processing tests should use deterministic fixtures for question-marker detection, OCR handling, crop boundaries, and segmentation confidence.
- Test negative paths: invalid input, unauthorized access, missing assignments, AI failure, low-confidence processing, and empty states.
- Do not weaken tests merely to make a change pass.
- Fix implementation defects instead of masking them in tests.

## Verification Output
State exactly which commands/tests were run and whether they passed. If something could not be verified, say why.
