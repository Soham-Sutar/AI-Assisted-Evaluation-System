# PROJECT_KNOWLEDGE.md

> **Refactor note:** This file preserves the relevant numbered sections of the original `GUIDE.md` verbatim and groups them by purpose. The original guide remains the source of truth; this file is the focused reading surface for the concern named above.

## Source coverage

- Section 1: 1. PROJECT IDENTITY
- Section 2: 2. PROBLEM STATEMENT
- Section 3: 3. PROJECT OBJECTIVES
- Section 4: 4. IMPORTANT SCOPE DEFINITION
- Section 5: 5. CORE CONCEPT
- Section 6: 6. USER ROLES
- Section 7: 7. RECOMMENDED TECHNOLOGY STACK
- Section 12: 12. EXAM CREATION WORKFLOW
- Section 13: 13. MODEL ANSWER MANAGEMENT
- Section 14: 14. ANSWER SHEET UPLOAD
- Section 26: 26. QUESTION-WISE DISTRIBUTION
- Section 27: 27. DYNAMIC FACULTY AVAILABILITY
- Section 28: 28. ASSIGNMENT DASHBOARD
- Section 29: 29. FACULTY DASHBOARD
- Section 34: 34. AI EXPLANATION
- Section 35: 35. AI CONFIDENCE
- Section 36: 36. AI EVALUATION TIMING
- Section 37: 37. DISCREPANCY / BIAS DETECTION
- Section 38: 38. FACULTY-LEVEL CONSISTENCY ANALYTICS
- Section 39: 39. QUESTION DIFFICULTY ANALYTICS
- Section 41: 41. REVIEW SCREEN
- Section 42: 42. FINAL SCORE CALCULATION
- Section 43: 43. FINAL RESULTS PAGE
- Section 44: 44. STUDENT DETAIL RESULT
- Section 45: 45. ADMIN DASHBOARD
- Section 46: 46. ANALYTICS DASHBOARD
- Section 47: 47. UI/UX DESIGN SYSTEM
- Section 48: 48. COLOR SYSTEM
- Section 49: 49. TYPOGRAPHY
- Section 50: 50. COMPONENTS
- Section 51: 51. RESPONSIVE DESIGN
- Section 52: 52. IMAGE VIEWER REQUIREMENTS
- Section 53: 53. ACCESSIBILITY
- Section 56: 56. PROCESSING STATUS UI
- Section 62: 62. SEED DATA
- Section 63: 63. DEMO MODE
- Section 64: 64. SAMPLE ANSWER SHEETS
- Section 71: 71. FACULTY FAIRNESS DESIGN
- Section 72: 72. AI/HUMAN COMPARISON PRINCIPLE
- Section 75: 75. NOTIFICATIONS
- Section 76: 76. EXPORTS
- Section 83: 83. ACCEPTANCE CRITERIA
- Section 85: 85. IMPORTANT PRODUCT BEHAVIOR
- Section 86: 86. EXAMPLE END-TO-END DEMO
- Section 96: 96. FUTURE EXTENSIONS
- Section 97: 97. REPORT/ACADEMIC POSITIONING
- Section 98: 98. UI PAGE DETAILS
- Section 99: 99. DESIGN FOR TRUST
- Section 100: 100. EVALUATION HISTORY
- Section 108: 108. MOST IMPORTANT REQUIREMENT
- Section 109: 109. END GOAL

---

# 1. PROJECT IDENTITY

## 1.1 Recommended title

**AI-Based Modular Answer Sheet Evaluation System with Bias Detection**

Alternative shorter product name:

**EvalAI – Modular Examination Evaluation Platform**

Use the full title in the project documentation and the shorter product name in the UI if desired.

---

---

# 2. PROBLEM STATEMENT

Traditional examination evaluation commonly follows a division-wise or batch-wise correction model. For example, one faculty member may correct all papers from Division A while another faculty member corrects all papers from Division B.

This creates several problems:

1. Different evaluators may interpret the marking scheme differently.
2. One evaluator may be stricter while another is more lenient.
3. Students answering the same question can receive different marks because of evaluator-specific grading tendencies.
4. Evaluating an entire answer sheet for many students creates a large workload for faculty.
5. It is difficult to identify inconsistent evaluation after the fact.
6. Manual aggregation of marks is time-consuming and error-prone.
7. There is little quantitative evidence to identify evaluator-level deviations.

The proposed system addresses these issues by changing the unit of evaluation from the **complete student paper** to the **individual question/answer**.

Instead of:

    Student 1 paper -> Faculty A
    Student 2 paper -> Faculty A
    Student 3 paper -> Faculty B

the system uses:

    Q1 of all students -> Faculty A
    Q2 of all students -> Faculty B
    Q3 of all students -> Faculty C

Thus, a faculty member evaluates the same question across many students, making the interpretation of that question's marking scheme more consistent.

The system also maintains an independent AI-assisted score for comparison and uses a review workflow for significant discrepancies.

---

---

# 3. PROJECT OBJECTIVES

The prototype must achieve these objectives:

### Primary objectives

- Accept scanned handwritten answer sheets.
- Support multiple students and multiple answer sheets.
- Process images using computer vision.
- Detect question boundaries.
- Segment/crop each answer into a separate image.
- Preserve the original answer-sheet image.
- Extract OCR text where possible.
- Store segmented answer images and metadata.
- Allow administrators to create examinations and questions.
- Upload model answers and marking schemes.
- Register faculty members and associate them with subjects.
- Track faculty availability/workload.
- Dynamically distribute question-evaluation work.
- Provide faculty-specific login.
- Show each faculty only the answers assigned to them.
- Allow faculty to enter marks and comments.
- Run AI-assisted evaluation against the model answer.
- Compare AI marks and faculty marks.
- Flag configurable discrepancies for review.
- Allow reviewer/re-evaluator intervention.
- Calculate final marks automatically.
- Provide dashboards and analytics.
- Maintain an audit trail of important actions.

### Secondary objectives

- Make the architecture scalable.
- Keep the AI evaluation module replaceable.
- Make segmentation debuggable.
- Provide a polished UI suitable for a final-year project demonstration.
- Use Docker for infrastructure and reproducible development.
- Provide seeded demo data so the system can be demonstrated without configuring everything manually.

---

---

# 4. IMPORTANT SCOPE DEFINITION

The prototype should be as close as possible to the intended final system, but it must clearly distinguish between:

### Fully implemented prototype functionality

- Authentication
- Role-based access
- Exam management
- Subject management
- Faculty management
- Student management
- Answer-sheet upload
- Image preprocessing
- Question detection
- Question-wise cropping
- OCR extraction
- Segmented answer storage
- Faculty allocation
- Faculty evaluation
- AI evaluation pipeline
- Score comparison
- Review workflow
- Final score aggregation
- Analytics
- Audit logging
- Dockerized PostgreSQL
- File/object storage abstraction
- API documentation

### AI limitations

Handwritten OCR and open-ended answer evaluation are inherently difficult. The system must therefore:

- never silently treat failed OCR as correct text;
- retain the original image;
- expose OCR confidence where available;
- allow manual correction of OCR text;
- show AI confidence;
- permit human override/review;
- never claim that a statistical discrepancy proves intentional bias.

The UI and documentation should use language such as:

**"Evaluation discrepancy detected"**

or

**"Potential evaluator inconsistency"**

rather than asserting that a faculty member is definitely biased.

---

---

# 5. CORE CONCEPT

The system has five major processing stages:

    1. INGESTION
       Scanned answer sheets
             |
             v
    2. DOCUMENT PROCESSING
       preprocessing + OCR + question detection
             |
             v
    3. MODULARIZATION
       question-wise answer images
             |
             v
    4. DISTRIBUTED EVALUATION
       faculty evaluation + AI evaluation
             |
             v
    5. MODERATION & RESULTS
       discrepancy detection + review + final marks

---

---

# 6. USER ROLES

Implement three primary roles.

## 6.1 ADMIN

The administrator controls the examination workflow.

Permissions:

- Login
- Dashboard
- Create examination
- Add subjects
- Add questions
- Set question marks
- Upload model answers
- Configure marking rubrics
- Add/import students
- Upload answer sheets
- Process answer sheets
- View segmentation results
- Approve/reject segmentation
- Manage faculty
- Set faculty subjects
- Set faculty availability
- Trigger assignment
- Reassign work
- View all evaluations
- View discrepancies
- Assign reviewers
- View final results
- View analytics
- Export reports
- View audit logs

## 6.2 FACULTY / EVALUATOR

Permissions:

- Login
- View personal dashboard
- View assigned questions/answers
- Filter by subject/examination/question/status
- Open answer image
- Zoom answer image
- View OCR text
- Correct OCR text if allowed
- View model answer/rubric according to configured permissions
- Enter marks
- Add comments
- Save draft
- Submit evaluation
- View evaluation history
- See completed/pending counts

Faculty must NOT be able to:

- access unrelated students' results;
- modify examination configuration;
- change another faculty member's marks;
- see private admin analytics unless explicitly permitted.

## 6.3 REVIEWER

Permissions:

- Login
- View flagged answers
- See original answer image
- See OCR
- See model answer/rubric
- See AI score
- See first faculty score
- Enter review/re-evaluation score
- Add review comment
- Resolve discrepancy
- Escalate issue
- Finalize reviewed answer

A reviewer can be a faculty member with reviewer privileges.

---

---

# 7. RECOMMENDED TECHNOLOGY STACK

Use the following stack unless a component is genuinely incompatible.

## Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- React Router
- TanStack Query
- React Hook Form
- Zod
- Recharts
- Lucide React icons

## Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic
- JWT authentication
- Passlib/bcrypt or Argon2 for password hashing
- Uvicorn

## Computer Vision

- OpenCV
- NumPy
- Pillow

## OCR

Prototype baseline:

- Tesseract OCR
- pytesseract

Design OCR behind an interface so another engine can be plugged in later.

Example interface:

    class OCRProvider:
        def extract(self, image) -> OCRResult:
            ...

## NLP / AI

- sentence-transformers
- scikit-learn
- spaCy where useful

Use a lightweight sentence-transformer model suitable for local prototype execution.

Recommended default:

    all-MiniLM-L6-v2

The AI module must be implemented as a service/module rather than hardcoded into API routes.

## Database

**PostgreSQL**

Use PostgreSQL in Docker.

Do not use SQLite for the primary implementation.

## Infrastructure

- Docker
- Docker Compose

At minimum run:

    postgres
    backend
    frontend

Optionally include:

    pgadmin

Do not make pgAdmin mandatory for normal operation.

## File storage

For the prototype, use a Docker-mounted persistent storage volume.

Recommended:

    backend/storage/original/
    backend/storage/processed/
    backend/storage/segmented/
    backend/storage/model_answers/

Mount this through Docker:

    ./storage:/app/storage

This means files persist even when containers are recreated.

The storage layer must be abstracted so S3/MinIO can be introduced later.

Optional future-compatible object storage:

- MinIO

If MinIO is included, make it optional and document it. PostgreSQL stores metadata; object storage stores images.

---

---

# 12. EXAM CREATION WORKFLOW

Admin creates:

    Examination
       |
       +-- Subject
       |
       +-- Questions
              |
              +-- Q1, marks
              +-- Q2, marks
              +-- Q3, marks
              |
              +-- model answer
              +-- rubric

Example:

    Examination: Internal Assessment 1
    Subject: Operating Systems

    Q1 - Explain process scheduling - 10 marks
    Q2 - Explain deadlock prevention - 10 marks
    Q3 - Compare paging and segmentation - 10 marks

---

---

# 13. MODEL ANSWER MANAGEMENT

Admin must be able to:

- create model answer;
- edit model answer;
- specify maximum marks;
- optionally create rubric points;
- specify marks per key point;
- save changes.

UI should support both:

### Simple mode

A single model answer text.

### Rubric mode

    Point 1: Definition       2 marks
    Point 2: Explanation       3 marks
    Point 3: Example           2 marks
    Point 4: Conclusion        3 marks

The AI evaluator should prefer rubric mode when available.

---

---

# 14. ANSWER SHEET UPLOAD

Admin upload UI must support:

- JPG
- JPEG
- PNG
- PDF

For prototype simplicity, scanned answer sheets should preferably be high-resolution PNG/JPEG or image-based PDFs.

Support:

- single upload;
- multiple upload;
- drag and drop;
- upload progress;
- file validation;
- preview;
- processing status.

The UI should allow mapping uploaded sheets to students.

Two options:

### Option A: filename mapping

Example:

    2022IS001.png
    2022IS002.png

Map register number from filename.

### Option B: manual mapping

Admin selects student after upload.

Implement filename parsing as the default and manual correction as fallback.

---

---

# 26. QUESTION-WISE DISTRIBUTION

The system should support two assignment modes.

## Mode 1: Question ownership

One faculty member is assigned an entire question.

Example:

    Q1 -> Faculty A
    Q2 -> Faculty B
    Q3 -> Faculty C

This is the preferred mode because it improves consistency.

## Mode 2: Question batch assignment

For very large classes, split a question's answer set into batches.

Example:

    Q1 answers 1-50 -> Faculty A
    Q1 answers 51-100 -> Faculty B

This should be an admin-configurable fallback.

Default to Mode 1.

---

---

# 27. DYNAMIC FACULTY AVAILABILITY

Faculty dashboard should contain:

    Available for Evaluation: ON/OFF

Admin can also control availability.

Each faculty has:

- max active assignments;
- current load;
- completed count.

If no eligible faculty is available:

    status = UNASSIGNED

Show an admin warning.

Do not silently assign to an ineligible faculty.

---

---

# 28. ASSIGNMENT DASHBOARD

Admin should see:

    Total Answers: 300
    Assigned: 270
    Unassigned: 30
    Completed: 120
    Pending: 150

Faculty workload table:

    Faculty       Subject       Assigned   Completed   Pending   Status
    Faculty A     DBMS          100        75          25        Available
    Faculty B     DBMS          100        80          20        Busy

Allow:

- auto assign;
- reassign;
- pause assignment;
- view assignment details.

---

---

# 29. FACULTY DASHBOARD

Faculty home page should show:

    Welcome, Dr. Faculty Name

Cards:

    Assigned: 100
    Completed: 75
    Pending: 25
    Reviewed: 0

Filters:

- Examination
- Subject
- Question
- Status

Primary section:

**My Evaluation Queue**

Columns:

    Student
    Question
    Max Marks
    Status
    Assigned At
    Action

Action:

    Evaluate

---

---

# 34. AI EXPLANATION

AI output should include structured explanation.

Example:

    {
      "covered_points": [
        "Correct definition",
        "Main working principle"
      ],
      "partial_points": [
        "Example"
      ],
      "missing_points": [
        "Advantages"
      ]
    }

UI:

    AI Evaluation

    Suggested Marks: 7.5 / 10
    Confidence: Medium

    Covered
      ✓ Correct definition
      ✓ Main working principle

    Partially Covered
      ~ Example

    Missing
      × Advantages

The AI explanation is advisory and must not automatically override the human evaluator.

---

---

# 35. AI CONFIDENCE

AI confidence should consider:

- OCR quality;
- answer length;
- semantic similarity;
- rubric coverage;
- ambiguity.

Use labels:

    High
    Medium
    Low

Example:

    High: 85%
    Medium: 65%
    Low: 40%

Document that this is a prototype confidence estimate, not a calibrated probability.

---

---

# 36. AI EVALUATION TIMING

To avoid influencing faculty:

1. AI can process answers after segmentation.
2. Store AI evaluation privately.
3. Faculty submits their score without seeing AI score.
4. After submission, the system compares scores.

Admin/reviewer can see both scores.

Optional configuration:

    reveal_ai_after_submission = true

Default:

    true

---

---

# 37. DISCREPANCY / BIAS DETECTION

The system must not state:

    "Faculty X is biased."

Instead it should identify:

    "Potential evaluation inconsistency detected."

For each evaluated answer:

    difference = abs(faculty_marks - ai_marks)

Normalize when useful:

    normalized_difference =
        difference / max_marks

Use configurable thresholds.

Example defaults:

    absolute threshold = 2 marks
    relative threshold = 20%

Flag when:

    absolute_difference >= threshold
    OR
    relative_difference >= relative_threshold

However, threshold should depend on max marks.

Example:

For 5-mark question:

    2 marks is a very large difference.

For 20-mark question:

    2 marks may not be large.

Therefore use relative difference as the primary rule.

---

---

# 38. FACULTY-LEVEL CONSISTENCY ANALYTICS

After sufficient evaluation data exists, calculate:

    mean(faculty_score - ai_score)

This gives average signed deviation.

Interpretation:

    positive -> faculty tends to award more than AI
    negative -> faculty tends to award less than AI

Also calculate:

- mean absolute deviation;
- median deviation;
- standard deviation;
- flagged percentage.

Display carefully:

    Evaluation Pattern

not:

    Bias Score

unless the report clearly explains that it is an indicator rather than proof of intentional bias.

---

---

# 39. QUESTION DIFFICULTY ANALYTICS

For each question calculate:

- average faculty marks;
- average AI marks;
- average percentage;
- standard deviation;
- number of attempts.

Example:

    Q1
    Average: 7.2 / 10
    Average percentage: 72%
    Difficulty indicator: Moderate

Do not claim scientifically validated difficulty unless a proper methodology is implemented.

---

---

# 41. REVIEW SCREEN

Show three cards:

### AI

    7.5 / 10

### Faculty

    4 / 10

### Difference

    3.5 marks
    FLAGGED

Below:

    Answer image

    Model answer

    Rubric

Reviewer form:

    Reviewed Marks
    Reviewer Comment

Buttons:

    Resolve
    Escalate

---

---

# 42. FINAL SCORE CALCULATION

For each student:

    Q1 final marks
    Q2 final marks
    Q3 final marks
    ...
    ----------------
    Total

Final marks rule:

### Normal answer

    final_marks = faculty_marks

### Reviewed answer

    final_marks = reviewer_marks

AI should not automatically replace faculty marks.

This is a human-in-the-loop system.

---

---

# 43. FINAL RESULTS PAGE

Admin can select an examination.

Display:

    Student        Q1   Q2   Q3   Q4   Total   Percentage
    -------------------------------------------------------
    Student A      8    7    9    6      30       75%
    Student B      6    8    7    7      28       70%

Features:

- search student;
- filter division;
- sort by marks;
- view answer-wise details;
- export CSV;
- export PDF if practical.

---

---

# 44. STUDENT DETAIL RESULT

When admin opens a student:

    Student information

    Examination information

    Question breakdown:

    Q1
      Faculty: Faculty A
      Faculty marks: 8
      AI marks: 7.5
      Final: 8
      Status: Normal

    Q2
      Faculty: Faculty B
      Faculty marks: 4
      AI marks: 7.5
      Final: 6
      Status: Reviewed

Show original/segmented answer image when authorized.

---

---

# 45. ADMIN DASHBOARD

Create a professional dashboard.

Header:

    EvalAI
    Examination Evaluation Platform

Sidebar:

    Dashboard
    Examinations
    Subjects
    Students
    Answer Sheets
    Segmentation
    Faculty
    Assignments
    Evaluations
    Review Queue
    Results
    Analytics
    Audit Logs
    Settings

Dashboard cards:

    Active Examinations
    Students
    Uploaded Sheets
    Segmented Answers
    Pending Evaluations
    Review Cases
    Completed Evaluations

Charts:

1. Evaluation completion
2. AI vs Faculty marks
3. Review cases by question
4. Faculty workload
5. Score distribution

---

---

# 46. ANALYTICS DASHBOARD

Include:

## Evaluation completion

    Uploaded: 200
    Segmented: 200
    Assigned: 200
    Evaluated: 150
    Reviewed: 10
    Remaining: 40

## Faculty workload

Bar chart:

    Faculty A -> 100
    Faculty B -> 80
    Faculty C -> 120

## AI vs Faculty

Scatter plot:

    X = AI marks
    Y = faculty marks

## Discrepancy distribution

Histogram or bar chart.

## Faculty evaluation pattern

Table:

    Faculty
    Answers evaluated
    Avg marks
    Avg AI marks
    Avg deviation
    Flag rate

Use neutral language.

---

---

# 47. UI/UX DESIGN SYSTEM

The interface should look like a professional SaaS application, not a basic college CRUD application.

## Design goals

- clean;
- modern;
- academic/professional;
- minimal;
- highly readable;
- responsive;
- accessible;
- desktop-first because faculty will evaluate on computers.

Avoid:

- excessive gradients;
- cartoon graphics;
- overly bright colors;
- unnecessary animations;
- huge decorative illustrations.

---

---

# 48. COLOR SYSTEM

Use a restrained professional palette.

Suggested:

- Primary: indigo/blue
- Background: neutral/slate
- Success: green
- Warning: amber
- Error: red
- Information: blue

Do not use color alone to convey status.

Example:

    ✓ Normal
    ⚠ Review Required
    ✕ Error

---

---

# 49. TYPOGRAPHY

Use a modern sans-serif font.

Recommended:

    Inter

Hierarchy:

    H1: 28-32px
    H2: 22-26px
    H3: 18-20px
    Body: 14-16px
    Metadata: 12-14px

Maintain consistent spacing.

---

---

# 50. COMPONENTS

Build reusable components:

- Sidebar
- Topbar
- StatCard
- DataTable
- SearchInput
- FilterBar
- StatusBadge
- Modal
- Drawer
- ConfirmDialog
- FileUploader
- ImageViewer
- ZoomControls
- EvaluationPanel
- RubricCard
- ScoreCard
- ProgressBar
- ChartCard
- EmptyState
- ErrorState
- LoadingSkeleton
- Toast notifications

---

---

# 51. RESPONSIVE DESIGN

Desktop:

    sidebar + main content

Tablet:

    collapsible sidebar

Mobile:

    bottom/slide-out navigation

However, prioritize desktop/tablet because answer evaluation requires a large screen.

---

---

# 52. IMAGE VIEWER REQUIREMENTS

The faculty image viewer must support:

- zoom;
- pan;
- fit-to-width;
- fit-to-height;
- rotate clockwise;
- rotate counterclockwise;
- reset;
- page switching for multi-page answers.

Never compress answer images unnecessarily.

---

---

# 53. ACCESSIBILITY

Implement:

- keyboard navigation;
- visible focus states;
- semantic labels;
- sufficient contrast;
- form error messages;
- accessible buttons;
- alt text where applicable.

---

---

# 56. PROCESSING STATUS UI

When an admin uploads a sheet:

    Uploading...
    Processing...
    OCR...
    Detecting Questions...
    Segmenting...
    Completed

For errors:

    Processing failed
    [View details] [Retry]

---

---

# 62. SEED DATA

Provide a demo dataset.

Create:

### Subjects

    Data Structures
    Operating Systems
    Database Management Systems

### Faculty

    Dr. Ananya Rao -> Data Structures
    Prof. Rahul Mehta -> Operating Systems
    Dr. Priya Shah -> DBMS

### Students

At least 10 demo students.

### Examination

    Internal Assessment - Demo

### Questions

At least 5 questions.

### Model answers

Provide realistic model answers and rubrics.

Do not require users to manually create all data just to see the prototype.

---

---

# 63. DEMO MODE

Add a clear "Demo Data" or seeded-data path.

The application should start with a usable demonstration environment after seeding.

Admin should be able to:

1. Login
2. Open demo examination
3. See students
4. See questions
5. See faculty
6. Upload/process sample sheets
7. See segmentation
8. Assign questions
9. Login as faculty
10. Evaluate
11. View review cases
12. See final results

---

---

# 64. SAMPLE ANSWER SHEETS

If no real handwriting samples are supplied, create a way to upload them.

Do not hardcode fake segmentation results.

The actual segmentation module must process the uploaded image.

For demo convenience, optionally provide sample answer-sheet images generated or placed under:

    storage/demo/

The system must treat them exactly like user uploads.

---

---

# 71. FACULTY FAIRNESS DESIGN

The system's most important conceptual principle is:

**Faculty members should evaluate the same question across students whenever possible.**

Therefore assignment should prioritize:

    question consistency
    subject eligibility
    workload balance

rather than randomly distributing entire student papers.

---

---

# 72. AI/HUMAN COMPARISON PRINCIPLE

The AI is a **reference evaluator**, not the final authority.

Use:

    AI score
       +
    Human score
       +
    Review mechanism

Do not automatically choose whichever score is higher or lower.

Final decision:

    Faculty score
    OR reviewer score if review occurs

---

---

# 75. NOTIFICATIONS

Implement in-app notifications.

Examples:

    12 new answers assigned to you.

    3 evaluations are pending.

    5 answers require review.

Use a notification bell in the topbar.

Email notifications are optional and not required for the prototype.

---

---

# 76. EXPORTS

Admin should be able to export:

### CSV

    student_register_number
    student_name
    Q1
    Q2
    Q3
    ...
    total
    percentage

### Faculty report

    faculty
    subject
    assigned
    completed
    pending
    average_marks
    flagged

### Review report

    answer
    faculty_score
    ai_score
    difference
    reviewer_score
    status

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

# 85. IMPORTANT PRODUCT BEHAVIOR

When admin uploads a paper:

    UPLOADED
       |
       v
    PROCESSING
       |
       +-- OCR
       |
       +-- SEGMENTATION
       |
       v
    NEEDS_REVIEW / PROCESSED

If processed:

    Answers become available.

Then:

    AUTO ASSIGN
       |
       v
    ASSIGNED

Faculty:

    ASSIGNED
       |
       v
    IN_PROGRESS
       |
       v
    COMPLETED

Then:

    AI score + faculty score
       |
       v
    discrepancy analysis

If normal:

    FINALIZED

If discrepancy:

    REVIEW_REQUIRED
       |
       v
    REVIEWED
       |
       v
    FINALIZED

---

---

# 86. EXAMPLE END-TO-END DEMO

Create a demo scenario.

Examination:

    Operating Systems

Questions:

    Q1 = 10 marks
    Q2 = 10 marks
    Q3 = 10 marks
    Q4 = 10 marks

Faculty:

    Faculty A -> Operating Systems
    Faculty B -> Operating Systems

Students:

    S001
    S002
    S003

Assignment:

    Q1 -> Faculty A
    Q2 -> Faculty B
    Q3 -> Faculty A
    Q4 -> Faculty B

Faculty A evaluates Q1 and Q3 for all students.

Faculty B evaluates Q2 and Q4 for all students.

AI independently evaluates all answers.

Example:

    S001 Q1:
        Faculty = 8
        AI = 7.6
        Difference = 0.4
        Status = Normal

    S001 Q2:
        Faculty = 4
        AI = 7.5
        Difference = 3.5
        Status = Review Required

Reviewer:

    Reviewer = 6

Final:

    Q1 = 8
    Q2 = 6
    Q3 = 7
    Q4 = 8
    Total = 29/40
    Percentage = 72.5%

---

---

# 96. FUTURE EXTENSIONS

Keep architecture ready for:

- better handwriting OCR;
- vision-language models;
- handwritten mathematical expression recognition;
- diagram analysis;
- multilingual OCR;
- multilingual answer evaluation;
- plagiarism detection;
- advanced statistical fairness analysis;
- S3/MinIO storage;
- university integration;
- LMS integration;
- student result portal;
- email notifications;
- mobile application.

Do not implement all future features now unless time permits.

---

---

# 97. REPORT/ACADEMIC POSITIONING

The project should be described as:

**A human-in-the-loop AI-assisted modular examination evaluation system.**

Do not claim:

- "AI eliminates human bias."
- "AI proves faculty bias."
- "AI completely replaces faculty."

Correct claims:

- "The system attempts to reduce evaluator workload."
- "The system promotes question-wise evaluation consistency."
- "The system detects potentially significant discrepancies."
- "The system provides AI-assisted reference scoring."
- "The system provides a structured review mechanism."

---

---

# 98. UI PAGE DETAILS

## Login

Centered card:

    EvalAI logo/name
    Email
    Password
    Remember me
    Login

Small footer:

    AI-Assisted Examination Evaluation

---

## Admin Dashboard

Top:

    Good morning, Admin

Cards:

    Active Exams
    Uploaded Sheets
    Pending Evaluations
    Review Cases

Middle:

    Evaluation Progress

Bottom:

    Recent Activity

---

## Examination Detail

Header:

    Operating Systems
    Internal Assessment 1
    Status: Evaluation

Tabs:

    Overview
    Questions
    Model Answers
    Answer Sheets
    Assignments
    Results
    Analytics

---

## Segmentation Review

Top:

    Examination selector
    Student selector
    Page selector

Main:

    Original page viewer

Overlay:

    Q1 boundary
    Q2 boundary
    Q3 boundary

Right:

    Detected answers

    Q1
    confidence High
    [Preview] [Edit]

    Q2
    confidence Medium
    [Preview] [Edit]

Buttons:

    Approve All
    Re-run Detection

---

## Faculty Queue

Table:

    Question
    Student
    Max Marks
    Status
    Action

Use a prominent:

    Evaluate

button.

---

## Evaluation Screen

Use large answer viewer.

Right panel stays visible while scrolling.

At bottom:

    Save Draft
    Submit Evaluation

After submit:

    Evaluation submitted successfully.

Do not reveal AI score until submission.

---

## Review Queue

Cards/table:

    Answer
    Student
    Question
    Faculty Score
    AI Score
    Difference
    Priority
    Status

Priorities:

    High
    Medium
    Low

---

---

# 99. DESIGN FOR TRUST

Because this system deals with student marks, trust is critical.

Every score should have provenance.

For each final mark, the admin should be able to answer:

    Who evaluated it?
    When?
    Was AI used?
    Was it reviewed?
    Who reviewed it?
    What was the original faculty score?
    What was the AI score?
    Why was it flagged?

Build an "Evaluation History" drawer for each answer.

---

---

# 100. EVALUATION HISTORY

Example:

    Q2 - Student S001

    10:30 AM
    Assigned to Faculty B

    11:10 AM
    Faculty B submitted 4/10

    11:12 AM
    AI evaluation: 7.5/10

    11:12 AM
    Discrepancy detected

    11:30 AM
    Assigned to Reviewer

    12:05 PM
    Reviewer submitted 6/10

    Final Score: 6/10

This feature greatly improves auditability.

---

---

# 108. MOST IMPORTANT REQUIREMENT

The prototype must demonstrate the complete real workflow rather than merely displaying mock dashboards.

The most important technical demonstration is:

**HANDWRITTEN IMAGE → REAL OCR/QUESTION DETECTION → REAL CROPPED ANSWER IMAGES → DATABASE → REAL FACULTY ASSIGNMENT → FACULTY LOGIN → REAL EVALUATION → AI REFERENCE SCORE → DISCREPANCY DETECTION → REVIEW → FINAL STUDENT MARKS**

If trade-offs are necessary, prioritize this workflow over cosmetic features.

The application should be stable, understandable, modular, and easy to extend into the final-year major project.

---

---

# 109. END GOAL

Build a production-style academic prototype that demonstrates how examination evaluation can be transformed from:

    "One faculty member evaluates one student's entire paper"

into:

    "Each question is evaluated consistently across students by an appropriate faculty member, while AI independently provides a reference evaluation and the system identifies potentially significant evaluation discrepancies."

The resulting platform must combine:

- Computer Vision
- OCR
- NLP
- Machine Learning
- Web Development
- Database Management
- Role-Based Access Control
- Workload Distribution
- Human-in-the-Loop AI
- Statistical Analytics
- Dockerized Infrastructure

The final prototype should be suitable for:

- final-year project demonstration;
- technical presentation;
- viva;
- future AI model improvements;
- conversion into a larger institutional examination system.
