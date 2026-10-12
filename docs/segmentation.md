# Segmentation
1. `cv/preprocessing.py`: EXIF-orient, grayscale, denoise, CLAHE, adaptive threshold (saved as *processed*), projection-profile deskew (±5°, 0.1° steps). Original never modified.
2. OCR pass 1: full page (psm 6). Pass 2 "blob re-read": isolated ink blobs in the left 30% not covered by confident words are cropped, Otsu-binarised,
   thickened and re-read as one line (psm 7, marker whitelist). Chosen by experiment: psm 8 on grey crops failed on isolated glyphs; this variant read them.
3. `cv/question_detector.py`: normalise tokens (`Q. 1`→`Q1`); patterns `Q1`, `Question 1:`, `1.`, `1)`; OCR digit confusions (`I,l,|,]`→1). Validate: left margin,
   OCR confidence ≥ threshold, number in the exam's configured set. Marker confidence = 0.65·OCR + 0.20·position + 0.15·known.
4. `select_marker_sequence`: drop bare numbers if prefixed markers exist; keep the max-confidence subsequence with strictly increasing numbers
   (rejects numbered sub-points inside answers, duplicates, out-of-order).
5. `cv/cropper.py`: start = marker top − padding; end = next marker top − padding; last = end of ink. Content above a page's first marker is a *continuation*
   only if real ink exists there; continuation crops are stacked into one image per question.
6. Per answer: OCR; blank detection (ink outside the marker box); segmentation confidence = marker conf × order factor × ink factor → High ≥0.75 / Medium ≥0.55 /
   Low (→ NEEDS_CORRECTION). Missing question ⇒ answer row with no image + NEEDS_CORRECTION.
Admin can approve, flag, re-run (blocked once assigned/evaluated) or set a manual vertical crop. Debug overlays are in `storage/debug`.

Bugs found and fixed by tests: continuation created from blank top margins; blank-answer false positive for one-line answers that start on the marker line;
false-positive markers from fragments of answer text (margin pass replaced by blob re-read).
