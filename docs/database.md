# Database (PostgreSQL, UUID keys, Alembic revision 0001)
users, subjects, faculty_subjects, examinations, questions, students, answer_sheets, answer_pages, answers, faculty_availability, assignments,
evaluations, ai_evaluations, review_cases, final_scores, audit_logs, **app_settings**.
Additions beyond GUIDE.md: `answers.{ocr_status,original_ocr_text,ocr_corrected,segmentation_label,segmentation_meta}`, `answer_pages.{debug_image_path,markers_json,deskew_angle}`,
`evaluations.is_draft`, `ai_evaluations.{status,error_message}`, `review_cases.{priority,note,created_at}`, `answer_sheets.processing_message`.
Indexes on FK/filter columns. One answer sheet per (student, exam) is enforced at the API level (not by a DB constraint).
