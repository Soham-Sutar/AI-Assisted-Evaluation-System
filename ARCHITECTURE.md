# ARCHITECTURE.md

> **Refactor note:** This file preserves the relevant numbered sections of the original `GUIDE.md` verbatim and groups them by purpose. The original guide remains the source of truth; this file is the focused reading surface for the concern named above.

## Source coverage

- Section 8: 8. HIGH-LEVEL ARCHITECTURE
- Section 9: 9. REPOSITORY STRUCTURE
- Section 10: 10. DATABASE DESIGN
- Section 11: 11. AUTHENTICATION
- Section 15: 15. IMAGE PROCESSING PIPELINE
- Section 16: 16. IMAGE PREPROCESSING
- Section 17: 17. QUESTION DETECTION
- Section 18: 18. IMPORTANT SEGMENTATION RULE
- Section 19: 19. MULTI-PAGE ANSWERS
- Section 20: 20. SEGMENTATION CONFIDENCE
- Section 21: 21. SEGMENTATION REVIEW UI
- Section 22: 22. DEBUG VISUALIZATION
- Section 23: 23. SEGMENTED IMAGE NAMING
- Section 24: 24. OCR PIPELINE
- Section 25: 25. FACULTY ASSIGNMENT ENGINE
- Section 30: 30. FACULTY EVALUATION SCREEN
- Section 31: 31. FACULTY EVALUATION RULES
- Section 32: 32. AI EVALUATION PIPELINE
- Section 33: 33. AI SCORING STRATEGY
- Section 54: 54. API DESIGN
- Section 55: 55. BACKGROUND PROCESSING
- Section 60: 60. DOCKER REQUIREMENTS
- Section 61: 61. DOCKER DATABASE INITIALIZATION
- Section 65: 65. SEGMENTATION ALGORITHM IMPLEMENTATION DETAIL
- Section 66: 66. SEGMENTATION PSEUDOCODE
- Section 67: 67. SEGMENTATION EDGE CASES
- Section 68: 68. AI MODULE STRUCTURE
- Section 77: 77. FRONTEND ROUTING
- Section 78: 78. FRONTEND STATE MANAGEMENT
- Section 80: 80. API DOCUMENTATION
- Section 87: 87. DATA FLOW
- Section 88: 88. CONFIGURATION
- Section 89: 89. DATABASE MIGRATIONS
- Section 92: 92. DATABASE INDEXES
- Section 106: 106. FINAL TECH STACK SUMMARY
- Section 107: 107. FINAL SYSTEM ARCHITECTURE

---

# 8. HIGH-LEVEL ARCHITECTURE

Use a clean separation:

    Browser
       |
       v
    React Frontend
       |
       | REST/JSON + multipart upload
       v
    FastAPI Backend
       |
       +----------------------+
       |                      |
       v                      v
    PostgreSQL           Processing Services
                              |
                 +------------+------------+
                 |            |            |
                 v            v            v
              OpenCV       Tesseract     AI/NLP
                 |
                 v
             Segmentation
                 |
                 v
          Persistent Storage

---

---

# 9. REPOSITORY STRUCTURE

Use a monorepo:

    evalai/
    |
    +-- frontend/
    |   +-- src/
    |   |   +-- components/
    |   |   +-- pages/
    |   |   +-- layouts/
    |   |   +-- hooks/
    |   |   +-- services/
    |   |   +-- types/
    |   |   +-- utils/
    |   |   +-- charts/
    |   |   +-- auth/
    |   |   +-- App.tsx
    |   |   +-- main.tsx
    |   +-- package.json
    |   +-- Dockerfile
    |
    +-- backend/
    |   +-- app/
    |   |   +-- main.py
    |   |   +-- core/
    |   |   |   +-- config.py
    |   |   |   +-- security.py
    |   |   |   +-- database.py
    |   |   +-- models/
    |   |   +-- schemas/
    |   |   +-- api/
    |   |   |   +-- auth.py
    |   |   |   +-- exams.py
    |   |   |   +-- subjects.py
    |   |   |   +-- students.py
    |   |   |   +-- faculty.py
    |   |   |   +-- uploads.py
    |   |   |   +-- segmentation.py
    |   |   |   +-- assignments.py
    |   |   |   +-- evaluations.py
    |   |   |   +-- reviews.py
    |   |   |   +-- results.py
    |   |   |   +-- analytics.py
    |   |   +-- services/
    |   |   |   +-- segmentation_service.py
    |   |   |   +-- ocr_service.py
    |   |   |   +-- assignment_service.py
    |   |   |   +-- evaluation_service.py
    |   |   |   +-- bias_service.py
    |   |   |   +-- result_service.py
    |   |   |   +-- storage_service.py
    |   |   +-- ai/
    |   |   |   +-- embeddings.py
    |   |   |   +-- rubric.py
    |   |   |   +-- scorer.py
    |   |   |   +-- confidence.py
    |   |   +-- cv/
    |   |   |   +-- preprocessing.py
    |   |   |   +-- question_detector.py
    |   |   |   +-- cropper.py
    |   |   |   +-- debug.py
    |   |   +-- workers/
    |   |   +-- utils/
    |   +-- alembic/
    |   +-- tests/
    |   +-- requirements.txt
    |   +-- Dockerfile
    |
    +-- storage/
    |   +-- original/
    |   +-- processed/
    |   +-- segmented/
    |   +-- model_answers/
    |   +-- exports/
    |   +-- debug/
    |
    +-- docker-compose.yml
    +-- .env.example
    +-- README.md
    +-- GUIDE.md

---

---

# 10. DATABASE DESIGN

Use PostgreSQL with UUID primary keys where practical.

## 10.1 users

Fields:

- id
- full_name
- email
- password_hash
- role
- is_active
- created_at
- updated_at

Roles:

    ADMIN
    FACULTY
    REVIEWER

## 10.2 subjects

Fields:

- id
- name
- code
- description
- created_at

Example:

    Data Structures
    Operating Systems
    Computer Networks

The system must not be restricted to these examples.

## 10.3 faculty_subjects

Many-to-many relationship:

- faculty_id
- subject_id

A faculty member may teach more than one subject if configured.

## 10.4 examinations

Fields:

- id
- name
- academic_year
- semester
- subject_id
- exam_date
- total_marks
- status
- created_at

Statuses:

    DRAFT
    READY
    PROCESSING
    EVALUATION
    REVIEW
    COMPLETED

## 10.5 questions

Fields:

- id
- examination_id
- question_number
- question_text
- max_marks
- model_answer_text
- rubric_json
- created_at

Example rubric:

    {
      "points": [
        {"description": "Correct definition", "marks": 2},
        {"description": "Core explanation", "marks": 3},
        {"description": "Example", "marks": 2},
        {"description": "Conclusion", "marks": 1}
      ]
    }

The rubric must be optional.

## 10.6 students

Fields:

- id
- register_number
- name
- division
- email
- created_at

## 10.7 answer_sheets

Fields:

- id
- examination_id
- student_id
- original_filename
- original_file_path
- page_count
- processing_status
- created_at

Statuses:

    UPLOADED
    PROCESSING
    PROCESSED
    FAILED
    NEEDS_REVIEW

## 10.8 answer_pages

Fields:

- id
- answer_sheet_id
- page_number
- image_path
- processed_image_path
- width
- height

## 10.9 answers

This is the core segmented-answer entity.

Fields:

- id
- answer_sheet_id
- student_id
- question_id
- page_start
- page_end
- image_path
- debug_image_path
- extracted_text
- ocr_confidence
- segmentation_confidence
- segmentation_status
- created_at
- updated_at

Statuses:

    DETECTED
    VERIFIED
    NEEDS_CORRECTION
    READY_FOR_EVALUATION

## 10.10 faculty_availability

Fields:

- id
- faculty_id
- is_available
- max_active_assignments
- current_assignment_count
- updated_at

## 10.11 assignments

Fields:

- id
- answer_id
- faculty_id
- assignment_type
- assigned_at
- started_at
- completed_at
- status

Assignment types:

    PRIMARY
    REEVALUATION
    REVIEW

Statuses:

    ASSIGNED
    IN_PROGRESS
    COMPLETED
    REASSIGNED
    CANCELLED

## 10.12 evaluations

Fields:

- id
- answer_id
- faculty_id
- assignment_id
- marks_awarded
- max_marks
- comments
- submitted_at
- version

## 10.13 ai_evaluations

Fields:

- id
- answer_id
- ai_marks
- confidence_score
- semantic_similarity
- keypoint_score
- final_ai_score
- explanation_json
- model_name
- created_at

## 10.14 review_cases

Fields:

- id
- answer_id
- trigger_type
- discrepancy_value
- status
- reviewer_id
- reviewer_marks
- reviewer_comments
- resolved_at

Trigger types:

    AI_HUMAN_DISCREPANCY
    LOW_AI_CONFIDENCE
    LOW_OCR_CONFIDENCE
    SEGMENTATION_ERROR
    MANUAL_FLAG

Statuses:

    OPEN
    ASSIGNED
    RESOLVED
    ESCALATED

## 10.15 final_scores

Fields:

- id
- student_id
- examination_id
- total_marks
- maximum_marks
- percentage
- status
- calculated_at

## 10.16 audit_logs

Fields:

- id
- user_id
- action
- entity_type
- entity_id
- metadata_json
- created_at

---

---

# 11. AUTHENTICATION

Implement secure authentication.

Use:

- email + password
- hashed passwords
- JWT access token

Frontend:

- store authentication state securely;
- protect routes;
- redirect unauthorized users;
- show role-specific navigation.

Backend:

- validate JWT on protected endpoints;
- enforce role permissions;
- never trust frontend role values.

Seed demo users:

    admin@example.com
    faculty1@example.com
    faculty2@example.com
    reviewer@example.com

Use obvious demo passwords only in development/seed data and document them clearly.

---

---

# 15. IMAGE PROCESSING PIPELINE

The segmentation system is a critical component.

Pipeline:

    Original Image
          |
          v
    Load / Normalize
          |
          v
    Grayscale
          |
          v
    Noise Reduction
          |
          v
    Contrast Enhancement
          |
          v
    Threshold / Binarization
          |
          v
    Deskew
          |
          v
    OCR
          |
          v
    Detect Question Markers
          |
          v
    Sort markers vertically
          |
          v
    Determine answer regions
          |
          v
    Crop
          |
          v
    Save segmented images
          |
          v
    OCR each segment
          |
          v
    Store metadata

---

---

# 16. IMAGE PREPROCESSING

Use OpenCV.

Recommended operations:

1. Load image.
2. Convert BGR to grayscale.
3. Resize only when necessary.
4. Apply Gaussian or median blur carefully.
5. Apply adaptive thresholding or Otsu thresholding.
6. Morphological opening/closing where required.
7. Detect page boundaries if useful.
8. Correct rotation/skew.

Do not aggressively alter the image used by faculty.

Maintain:

    original_image
    processed_image

Faculty should normally see the original or high-quality processed crop, not an unreadable binary image.

---

---

# 17. QUESTION DETECTION

The prototype must support common question-marker patterns:

    Q1
    Q.1
    Q 1
    Q-1
    1.
    1)
    1 )
    Question 1
    QUESTION 1

Use OCR text and coordinates.

Tesseract's word-level data should provide:

- text
- confidence
- x
- y
- width
- height

Normalize OCR text before matching.

Example normalization:

    "Q. 1" -> "Q1"
    "Q-1"  -> "Q1"

Use regular expressions.

Example conceptual patterns:

    ^q[\s.\-_:]*([0-9]+)
    ^question[\s.\-_:]*([0-9]+)
    ^([0-9]{1,2})[.)]

Do not assume that every number on a page is a question number.

Use contextual checks:

- marker should be near the left margin;
- marker should be near a plausible answer-start region;
- marker confidence should exceed a configurable threshold;
- question number should belong to the examination's configured question set.

---

---

# 18. IMPORTANT SEGMENTATION RULE

For each detected question marker:

    Start Y = marker's top Y

    End Y = next detected question marker's top Y

For the last question:

    End Y = bottom of page

Add configurable padding:

    top_padding
    bottom_padding
    left_padding
    right_padding

Do not crop too tightly.

The output must preserve enough context for a faculty member to read the complete answer.

---

---

# 19. MULTI-PAGE ANSWERS

The system must support a question continuing onto the next page.

Prototype strategy:

- detect questions per page;
- if a page contains no new question marker, treat the page content as continuation of the previous question;
- merge consecutive segments belonging to the same question;
- generate one combined image for that answer when possible.

Example:

    Page 1:
       Q1
       answer...
       Q2
       answer...

    Page 2:
       continuation of Q2
       answer...
       Q3
       answer...

Output:

    Q1 -> image
    Q2 -> combined image from page 1 + page 2
    Q3 -> image

Implement a robust but explainable heuristic.

---

---

# 20. SEGMENTATION CONFIDENCE

Each segmentation result should have a confidence score.

Possible factors:

- OCR confidence of marker;
- confidence that marker matches a configured question;
- expected ordering;
- left-margin position;
- spacing plausibility;
- presence of handwriting/text below marker.

Do not pretend this is a scientifically calibrated probability.

Label it:

**Segmentation confidence**

with values such as:

    High
    Medium
    Low

Low-confidence segments should be shown to admin for verification.

---

---

# 21. SEGMENTATION REVIEW UI

Admin should have a page:

**Segmentation Review**

Show:

- original page on left;
- detected question markers;
- crop boundaries;
- segmented answer thumbnails on right.

Allow admin to:

- approve;
- change question number;
- adjust crop boundary;
- split a segment;
- merge two segments;
- re-run segmentation;
- mark as needs manual correction.

This is highly important because handwritten documents will not always follow perfect formatting.

---

---

# 22. DEBUG VISUALIZATION

Generate optional debug images.

Example:

    original page
       |
       +-- red marker at Q1
       +-- red marker at Q2
       +-- green crop boundaries

Save under:

    storage/debug/

Allow admin to open the debug image.

---

---

# 23. SEGMENTED IMAGE NAMING

Use deterministic names.

Example:

    EXAM001_STU2022IS001_Q1.png
    EXAM001_STU2022IS001_Q2.png

For multiple pages internally:

    EXAM001_STU2022IS001_Q2_P1.png

If merged:

    EXAM001_STU2022IS001_Q2.png

Do not rely on filenames as the source of truth. Database IDs are authoritative.

---

---

# 24. OCR PIPELINE

OCR is used for two purposes:

1. question detection;
2. AI evaluation text extraction.

Use Tesseract initially.

The OCR service must return:

    text
    confidence
    bounding_boxes

Store the OCR text with the answer.

If OCR confidence is low:

    status = NEEDS_CORRECTION

Admin/faculty may manually correct extracted text if permitted.

Always keep the original image.

---

---

# 25. FACULTY ASSIGNMENT ENGINE

The assignment engine distributes answers by question.

The key rule:

**A faculty member can receive an answer only if they are eligible for that subject.**

Eligibility:

    faculty is active
    AND faculty is available
    AND faculty teaches the examination subject

If multiple faculty members are eligible, use workload balancing.

Recommended algorithm:

    score = current_load / max_capacity

Choose the eligible faculty with the lowest score.

Tie-break using round-robin.

This is better than simply assigning randomly.

---

---

# 30. FACULTY EVALUATION SCREEN

This is one of the most important UI screens.

Use a two-column layout.

### Left panel: answer

- Large answer image
- Zoom in/out
- Fit to screen
- Rotate
- Previous/next answer
- Page navigation for multi-page answer

### Right panel: evaluation

Show:

    Student: STU001
    Subject: Operating Systems
    Question: Q2
    Maximum Marks: 10

Model answer:

    [expandable panel]

Rubric:

    Definition       2
    Explanation      3
    Example          2
    Accuracy         3

Faculty input:

    Marks: [ 0 - 10 ]
    Comments: [ textarea ]

Buttons:

    Save Draft
    Submit Evaluation

Do not expose the AI score before the faculty submits their independent score if the purpose is to avoid influencing the evaluator.

This is important for a fair comparison.

---

---

# 31. FACULTY EVALUATION RULES

Validate:

    marks >= 0
    marks <= max_marks

Once submitted:

- lock the original evaluation;
- create a new version if editing is permitted;
- record timestamp;
- record faculty ID.

Do not overwrite history.

---

---

# 32. AI EVALUATION PIPELINE

The AI evaluation should operate independently.

Input:

    student_answer_text
    model_answer_text
    max_marks
    optional_rubric

Output:

    ai_marks
    confidence
    semantic_similarity
    keypoint_score
    explanation
    model_name

---

---

# 33. AI SCORING STRATEGY

Do not use simple keyword matching alone.

Use a hybrid approach.

## Stage 1: Semantic similarity

Use Sentence Transformer embeddings.

Conceptually:

    student_embedding = model.encode(student_answer)
    model_embedding = model.encode(model_answer)

Then:

    similarity = cosine_similarity(
        student_embedding,
        model_embedding
    )

Normalize to 0-1.

## Stage 2: Key-point matching

If rubric exists:

- embed each rubric point;
- compare each point with the student's answer;
- determine whether the point is covered;
- calculate weighted coverage.

Example:

    Point A = 2 marks
    Point B = 3 marks
    Point C = 5 marks

If:

    A covered
    B partially covered
    C not covered

AI score may be approximately:

    2 + 1.5 + 0 = 3.5 / 10

Use explainable intermediate values.

## Stage 3: Final score

Recommended prototype formula:

    semantic_component = similarity * 0.50

    keypoint_component = keypoint_score * 0.50

    normalized_ai_score =
        semantic_component + keypoint_component

    ai_marks =
        round(normalized_ai_score * max_marks, 1)

This formula must be configurable.

Do NOT use a fake formula such as "similarity * 5 + keyword * 5" without normalizing the components.

---

---

# 54. API DESIGN

Use REST APIs.

## Authentication

    POST /api/auth/login
    POST /api/auth/register
    GET  /api/auth/me

## Subjects

    GET /api/subjects
    POST /api/subjects
    PUT /api/subjects/{id}
    DELETE /api/subjects/{id}

## Exams

    GET /api/exams
    POST /api/exams
    GET /api/exams/{id}
    PUT /api/exams/{id}

## Questions

    GET /api/exams/{exam_id}/questions
    POST /api/exams/{exam_id}/questions
    PUT /api/questions/{id}

## Model answers

    POST /api/questions/{id}/model-answer
    PUT /api/questions/{id}/model-answer

## Students

    GET /api/students
    POST /api/students
    POST /api/students/import

## Answer sheets

    POST /api/answer-sheets/upload
    GET /api/answer-sheets
    GET /api/answer-sheets/{id}
    POST /api/answer-sheets/{id}/process

## Segmentation

    POST /api/answers/{id}/resegment
    GET /api/answer-sheets/{id}/segments
    PUT /api/answers/{id}/segmentation
    POST /api/answers/{id}/approve

## Faculty

    GET /api/faculty
    POST /api/faculty
    PUT /api/faculty/{id}
    POST /api/faculty/{id}/availability

## Assignments

    POST /api/assignments/auto-assign
    GET /api/assignments
    GET /api/faculty/me/assignments
    POST /api/assignments/{id}/reassign

## Evaluations

    POST /api/evaluations
    PUT /api/evaluations/{id}
    GET /api/answers/{id}/evaluation

## AI

    POST /api/answers/{id}/ai-evaluate
    GET /api/answers/{id}/ai-evaluation

## Review

    GET /api/reviews
    POST /api/reviews/{id}/assign
    POST /api/reviews/{id}/resolve

## Results

    GET /api/exams/{id}/results
    GET /api/exams/{id}/students/{student_id}/result
    POST /api/exams/{id}/calculate-results

## Analytics

    GET /api/analytics/exams/{id}
    GET /api/analytics/faculty/{id}

---

---

# 55. BACKGROUND PROCESSING

Image processing and AI inference can be slow.

Do not block HTTP requests for large batches.

For the prototype, implement a simple background processing mechanism.

Options:

### Preferred prototype

FastAPI BackgroundTasks for small demonstrations.

### Scalable option

Redis + Celery/RQ.

If using Docker and the implementation remains manageable, Redis + Celery is preferred for the final architecture.

Services:

    frontend
    backend
    worker
    redis
    postgres

Worker jobs:

    process_answer_sheet
    segment_page
    run_ocr
    run_ai_evaluation
    calculate_analytics

The UI must display processing status.

---

---

# 60. DOCKER REQUIREMENTS

Provide:

    docker-compose.yml

Services:

    postgres
    backend
    frontend

Optional:

    redis
    worker
    pgadmin

PostgreSQL volume:

    postgres_data:/var/lib/postgresql/data

Application storage volume:

    ./storage:/app/storage

Use environment variables:

    POSTGRES_DB
    POSTGRES_USER
    POSTGRES_PASSWORD
    DATABASE_URL
    JWT_SECRET
    STORAGE_PATH
    OCR_LANGUAGE
    AI_MODEL_NAME

Create:

    .env.example

Do not commit real secrets.

---

---

# 61. DOCKER DATABASE INITIALIZATION

The backend must run migrations automatically or provide a documented migration command.

Use Alembic.

Initial startup:

    docker compose up --build

Then:

    migrations
    seed demo data

The README must explain how to run the project from zero.

---

---

# 65. SEGMENTATION ALGORITHM IMPLEMENTATION DETAIL

Create:

    backend/app/cv/preprocessing.py
    backend/app/cv/question_detector.py
    backend/app/cv/cropper.py

### preprocessing.py

Functions:

    load_image()
    to_grayscale()
    denoise()
    threshold()
    deskew()
    preprocess_for_ocr()

### question_detector.py

Functions:

    extract_ocr_data()
    normalize_ocr_token()
    detect_question_marker()
    detect_question_markers()
    validate_marker()
    sort_markers()

Return structured objects:

    QuestionMarker(
        question_number,
        x,
        y,
        width,
        height,
        confidence
    )

### cropper.py

Functions:

    calculate_crop_regions()
    crop_answer()
    merge_multipage_answer()
    save_segment()

---

---

# 66. SEGMENTATION PSEUDOCODE

Conceptually:

    image = load_image(path)

    processed = preprocess_for_ocr(image)

    ocr_data = ocr.extract(processed)

    markers = detect_question_markers(
        ocr_data,
        configured_questions
    )

    markers = sort_markers(markers)

    for index, marker in enumerate(markers):

        start_y = marker.y - top_padding

        if index < len(markers) - 1:
            end_y = markers[index + 1].y - separator_padding
        else:
            end_y = image.height - bottom_padding

        crop = image[
            start_y:end_y,
            left_padding:right_padding
        ]

        save(crop)

The implementation must include bounds checking.

---

---

# 67. SEGMENTATION EDGE CASES

Handle:

- no question markers;
- duplicate question marker;
- marker OCR error;
- question numbers out of order;
- missing question;
- continuation page;
- very large answer;
- answer begins near page top;
- question marker at bottom;
- multiple question markers close together;
- blank answer;
- crossed-out content.

If segmentation confidence is low, require admin verification.

---

---

# 68. AI MODULE STRUCTURE

Create:

    ai/
      embeddings.py
      rubric.py
      scorer.py
      confidence.py

### embeddings.py

Load sentence-transformer model once.

Do not reload the model for every answer.

### scorer.py

Implement:

    evaluate_answer(
        student_text,
        model_answer,
        max_marks,
        rubric
    )

Return structured result.

### rubric.py

Implement key-point matching.

### confidence.py

Calculate prototype confidence.

---

---

# 77. FRONTEND ROUTING

Suggested routes:

    /login

    /admin/dashboard
    /admin/exams
    /admin/exams/:id
    /admin/exams/:id/questions
    /admin/students
    /admin/faculty
    /admin/answersheets
    /admin/segmentation
    /admin/assignments
    /admin/evaluations
    /admin/reviews
    /admin/results
    /admin/analytics
    /admin/audit-logs
    /admin/settings

    /faculty/dashboard
    /faculty/assignments
    /faculty/evaluate/:answerId

    /reviewer/dashboard
    /reviewer/reviews
    /reviewer/review/:reviewId

---

---

# 78. FRONTEND STATE MANAGEMENT

Use TanStack Query for server state.

Use React local state/context for:

- authentication;
- UI state;
- filters;
- modals.

Avoid creating an unnecessarily complex global state system.

---

---

# 80. API DOCUMENTATION

FastAPI should automatically expose:

    /docs

and:

    /redoc

The README should link to the local API documentation.

---

---

# 87. DATA FLOW

Complete data flow:

    Student
       |
       v
    Answer Sheet
       |
       v
    Upload
       |
       v
    Original File Storage
       |
       v
    Page Extraction
       |
       v
    Image Preprocessing
       |
       v
    OCR
       |
       v
    Question Detection
       |
       v
    Answer Segmentation
       |
       +-------> Segmented Image
       |
       +-------> OCR Text
       |
       +-------> Confidence
       |
       v
    Database
       |
       v
    Assignment Engine
       |
       +------------+
       |            |
       v            v
    Faculty       AI Engine
       |            |
       |            v
       |        AI Score
       |            |
       v            |
    Faculty Score   |
       |            |
       +-------> Comparison
                    |
             +------+------+
             |             |
           Normal        Flagged
             |             |
             |             v
             |          Reviewer
             |             |
             +------+------+
                    |
                    v
               Final Score
                    |
                    v
                Analytics
                    |
                    v
                 Reports

---

---

# 88. CONFIGURATION

Provide `.env.example`:

    APP_ENV=development

    DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/evalai

    JWT_SECRET=change-me

    STORAGE_PATH=/app/storage

    OCR_LANGUAGE=eng

    AI_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

    AI_DEVICE=auto

    AI_SEMANTIC_WEIGHT=0.5
    AI_KEYPOINT_WEIGHT=0.5

    REVIEW_ABSOLUTE_THRESHOLD=2
    REVIEW_RELATIVE_THRESHOLD=0.20

    MAX_UPLOAD_MB=50

---

---

# 89. DATABASE MIGRATIONS

Use Alembic.

Create migrations for all tables.

Do not use:

    Base.metadata.create_all()

as the only production schema mechanism.

For local development, migrations should be easy to run.

---

---

# 92. DATABASE INDEXES

Add indexes for:

    answer_sheets.examination_id
    answers.student_id
    answers.question_id
    assignments.faculty_id
    assignments.status
    evaluations.answer_id
    review_cases.status
    final_scores.examination_id
    final_scores.student_id

---

---

# 106. FINAL TECH STACK SUMMARY

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite |
| Styling | Tailwind CSS |
| UI Components | shadcn/ui |
| Routing | React Router |
| Server State | TanStack Query |
| Charts | Recharts |
| Backend | FastAPI |
| Language | Python |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Database | PostgreSQL |
| Migrations | Alembic |
| Authentication | JWT |
| Computer Vision | OpenCV |
| OCR | Tesseract + pytesseract |
| NLP | sentence-transformers |
| ML utilities | scikit-learn |
| Optional NLP | spaCy |
| Async processing | FastAPI BackgroundTasks or Celery |
| Queue | Redis if Celery is used |
| Containers | Docker + Docker Compose |
| Storage | Docker persistent volume; optional MinIO abstraction |
| API docs | FastAPI Swagger/OpenAPI |

---

---

# 107. FINAL SYSTEM ARCHITECTURE

The finished system should conceptually look like:

                         ┌──────────────────────┐
                         │      ADMIN           │
                         │ Exam / Faculty /     │
                         │ Upload / Results     │
                         └──────────┬───────────┘
                                    |
                                    v
                         ┌──────────────────────┐
                         │   REACT FRONTEND     │
                         └──────────┬───────────┘
                                    |
                                    v
                         ┌──────────────────────┐
                         │    FASTAPI BACKEND   │
                         └───────┬───────┬──────┘
                                 |       |
                ┌────────────────┘       └────────────────┐
                v                                         v
       ┌─────────────────┐                       ┌─────────────────┐
       │   PostgreSQL    │                       │  File Storage   │
       │                 │                       │                 │
       │ users           │                       │ originals       │
       │ exams           │                       │ processed       │
       │ questions       │                       │ segmented       │
       │ answers         │                       │ model answers   │
       │ assignments     │                       │ debug           │
       │ evaluations     │                       └─────────────────┘
       │ reviews         │
       │ results         │
       └─────────────────┘

                         Processing Layer
                                 |
                ┌────────────────┼─────────────────┐
                v                v                 v
          ┌───────────┐   ┌────────────┐   ┌──────────────┐
          │  OpenCV   │   │ Tesseract  │   │ AI/NLP       │
          │           │   │            │   │              │
          │ preprocess│   │ OCR        │   │ embeddings   │
          │ deskew    │   │ coordinates│   │ similarity   │
          │ crop      │   │ text       │   │ rubric       │
          └─────┬─────┘   └─────┬──────┘   └──────┬───────┘
                |                |                 |
                └────────────────┼─────────────────┘
                                 v
                      ┌──────────────────────┐
                      │ Question-wise        │
                      │ Answer Units         │
                      └──────────┬───────────┘
                                 |
                                 v
                      ┌──────────────────────┐
                      │ Assignment Engine    │
                      │ Subject + Workload   │
                      └──────────┬───────────┘
                                 |
                     ┌───────────┴────────────┐
                     v                        v
             ┌──────────────┐          ┌──────────────┐
             │   FACULTY    │          │   AI ENGINE  │
             │   SCORE      │          │   SCORE      │
             └──────┬───────┘          └──────┬───────┘
                    |                         |
                    └────────────┬────────────┘
                                 v
                       ┌────────────────────┐
                       │ Discrepancy Engine │
                       └─────────┬──────────┘
                                 |
                    ┌────────────┴────────────┐
                    v                         v
                 NORMAL                    FLAGGED
                    |                         |
                    |                         v
                    |                    ┌──────────┐
                    |                    │ REVIEWER │
                    |                    └────┬─────┘
                    |                         |
                    └────────────┬────────────┘
                                 v
                       ┌────────────────────┐
                       │  FINAL SCORE       │
                       │  AGGREGATION       │
                       └─────────┬──────────┘
                                 |
                                 v
                       ┌────────────────────┐
                       │ Results + Reports │
                       │ + Analytics        │
                       └────────────────────┘

---
