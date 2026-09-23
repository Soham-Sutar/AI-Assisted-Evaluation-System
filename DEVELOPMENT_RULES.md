# DEVELOPMENT_RULES.md

> **Refactor note:** This file preserves the relevant numbered sections of the original `GUIDE.md` verbatim and groups them by purpose. The original guide remains the source of truth; this file is the focused reading surface for the concern named above.

## Source coverage

- Section 40: 40. REVIEW WORKFLOW
- Section 57: 57. ERROR HANDLING
- Section 58: 58. SECURITY
- Section 59: 59. FILE SECURITY
- Section 69: 69. AI MODEL PERFORMANCE
- Section 70: 70. OCR PERFORMANCE
- Section 73: 73. REVIEW THRESHOLD CONFIGURATION
- Section 74: 74. AUDIT LOGGING
- Section 79: 79. FORM VALIDATION
- Section 81: 81. TESTING
- Section 82: 82. SEGMENTATION TEST CASES
- Section 84: 84. IMPORTANT IMPLEMENTATION PRINCIPLES
- Section 90: 90. LOGGING
- Section 91: 91. PERFORMANCE REQUIREMENTS
- Section 93: 93. API ERROR FORMAT
- Section 94: 94. UI ERROR MESSAGES
- Section 95: 95. MANUAL FALLBACK
- Section 101: 101. IMPORTANT UX RULE FOR AI
- Section 103: 103. DEVELOPMENT RULES FOR THE AI CODING AGENT
- Section 105: 105. DOCUMENTATION REQUIREMENTS

---

# 40. REVIEW WORKFLOW

When an answer is flagged:

    Faculty evaluation
          |
          v
    Discrepancy detected
          |
          v
    Review case created
          |
          v
    Reviewer assigned
          |
          v
    Reviewer sees:
        answer image
        model answer
        rubric
        faculty score
        AI score
        discrepancy
          |
          v
    Reviewer enters final/review score
          |
          v
    Case resolved
          |
          v
    Final score updated

---

---

# 57. ERROR HANDLING

Every module must fail gracefully.

Examples:

### OCR failure

    OCR could not confidently process this answer.
    Original image retained.
    Manual text entry available.

### Segmentation failure

    No reliable question markers detected.
    Manual segmentation required.

### No eligible faculty

    No available faculty found for this subject.
    Assignment remains pending.

### AI failure

    AI evaluation unavailable.
    Faculty evaluation can continue.

AI failure must never block human evaluation.

---

---

# 58. SECURITY

Implement:

- password hashing;
- JWT;
- role-based authorization;
- input validation;
- file type validation;
- file size limits;
- secure filenames;
- path traversal protection;
- authorization checks for image access;
- CORS configuration;
- environment variables for secrets.

Never store passwords in plaintext.

Never expose database credentials to frontend.

---

---

# 59. FILE SECURITY

Uploaded files must be stored outside frontend static source directories.

Use generated storage paths.

Do not trust uploaded filenames.

Validate:

- extension;
- MIME type;
- file size.

Example maximum:

    20 MB per image
    50 MB per PDF

Make limits configurable.

---

---

# 69. AI MODEL PERFORMANCE

Use lazy model initialization.

Cache the loaded model.

If GPU is available, allow configuration.

Otherwise CPU must work.

Environment:

    AI_DEVICE=cpu

or:

    AI_DEVICE=auto

---

---

# 70. OCR PERFORMANCE

For large batches:

- process asynchronously;
- avoid OCRing the same image repeatedly;
- cache OCR results;
- store results in database.

---

---

# 73. REVIEW THRESHOLD CONFIGURATION

Create an admin settings section:

    Review Configuration

Fields:

    Relative discrepancy threshold: 20%
    Absolute discrepancy threshold: 2 marks
    Minimum confidence for automatic AI acceptance: optional
    Low OCR threshold: 60%
    Low segmentation threshold: 60%

These values must be configurable.

---

---

# 74. AUDIT LOGGING

Record important actions:

    User logged in
    Examination created
    Model answer changed
    Answer sheet uploaded
    Segmentation executed
    Segmentation manually modified
    Assignment created
    Assignment reassigned
    Faculty evaluation submitted
    AI evaluation generated
    Review case created
    Review resolved
    Final marks calculated

Admin can filter logs by:

- user;
- action;
- date;
- entity.

---

---

# 79. FORM VALIDATION

Use:

- React Hook Form
- Zod

Validate:

- email;
- password;
- marks;
- max marks;
- question numbers;
- required fields;
- upload files.

---

---

# 81. TESTING

Implement tests.

## Backend unit tests

Test:

- question marker detection;
- OCR normalization;
- crop boundary calculation;
- faculty assignment;
- score calculation;
- discrepancy detection;
- final score aggregation.

## API tests

Test:

- login;
- authorization;
- uploads;
- assignments;
- evaluations;
- reviews;
- results.

## Frontend tests

At minimum test:

- login;
- role-based route access;
- evaluation form;
- marks validation.

---

---

# 82. SEGMENTATION TEST CASES

Create test images or fixtures covering:

1. Q1/Q2/Q3 standard layout.
2. "Question 1" format.
3. "1." format.
4. Irregular spacing.
5. Multi-page answer.
6. Missing question number.
7. OCR error.
8. Multiple students.
9. Blank answer.
10. Last question ending at bottom.

---

---

# 84. IMPORTANT IMPLEMENTATION PRINCIPLES

## Principle 1: Do not fake AI

Do not hardcode:

    AI score = 7

The score must actually be generated from the answer and model answer.

## Principle 2: Do not fake segmentation

Do not create predetermined crops.

The uploaded image must actually be processed.

## Principle 3: Do not fake faculty assignment

Assignment must query actual faculty records and workload.

## Principle 4: Do not fake final results

Final marks must be calculated from stored evaluations.

## Principle 5: Preserve original data

Never destroy original answer-sheet images.

## Principle 6: Human evaluation remains authoritative

AI is advisory.

## Principle 7: Make every stage observable

The admin should be able to see:

    uploaded
    processed
    segmented
    assigned
    evaluated
    reviewed
    finalized

---

---

# 90. LOGGING

Backend logs should include:

- request errors;
- upload processing;
- segmentation events;
- OCR errors;
- AI errors;
- assignment events.

Do not log:

- passwords;
- JWT tokens;
- sensitive authentication data.

---

---

# 91. PERFORMANCE REQUIREMENTS

Prototype target:

- process one answer sheet reliably;
- process batches asynchronously;
- avoid loading all high-resolution images into memory at once;
- cache AI model;
- cache OCR results;
- paginate database queries;
- paginate faculty assignments.

Frontend:

- lazy-load large images;
- show thumbnails before full image;
- avoid rendering hundreds of full-resolution images simultaneously.

---

---

# 93. API ERROR FORMAT

Use a consistent response format.

Example:

    {
      "success": false,
      "error": {
        "code": "SEGMENTATION_FAILED",
        "message": "No reliable question markers were detected."
      }
    }

Do not expose internal stack traces to users.

---

---

# 94. UI ERROR MESSAGES

Use human-readable messages.

Bad:

    500 Internal Server Error

Better:

    "We could not process this answer sheet. The original file is safe. Try processing again or open it for manual segmentation."

---

---

# 95. MANUAL FALLBACK

The prototype must include a manual fallback because handwriting and OCR cannot be guaranteed.

Admin can manually specify:

    question number
    crop start
    crop end

or use a simple interactive crop tool.

Manual segmentation should create the same `answers` records as automatic segmentation.

This makes the system usable even when automatic segmentation fails.

---

---

# 101. IMPORTANT UX RULE FOR AI

Do not show AI recommendations before independent faculty submission.

After faculty submission, optionally show:

    AI Reference Evaluation

This prevents the AI score from anchoring the faculty's judgement.

---

---

# 103. DEVELOPMENT RULES FOR THE AI CODING AGENT

The coding agent must:

1. Build a genuinely working full-stack application.
2. Do not create placeholder buttons that do nothing.
3. Do not hardcode database records into frontend components.
4. Do not hardcode segmentation outputs.
5. Do not hardcode AI marks.
6. Use real API calls.
7. Use PostgreSQL.
8. Use Docker.
9. Keep secrets in environment variables.
10. Implement migrations.
11. Include seed data.
12. Include error handling.
13. Include loading states.
14. Include empty states.
15. Include proper authentication.
16. Keep AI/CV logic modular.
17. Preserve original answer images.
18. Keep an audit trail.
19. Make the application runnable with documented Docker commands.
20. Make the core demo work from start to finish.

---

---

# 105. DOCUMENTATION REQUIREMENTS

Generate:

    README.md

containing:

- project description;
- architecture;
- prerequisites;
- Docker installation;
- setup;
- environment variables;
- migrations;
- seed command;
- startup;
- demo credentials;
- API docs;
- troubleshooting;
- project structure.

Also include:

    docs/
      architecture.md
      segmentation.md
      ai-evaluation.md
      database.md
      api.md

---
