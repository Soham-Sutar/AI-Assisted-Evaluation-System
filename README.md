# EvalAI

**AI-Based Modular Answer Sheet Evaluation System with Bias Detection**

EvalAI is a human-in-the-loop examination evaluation platform that processes handwritten answer sheets through OCR and computer-vision segmentation, distributes question-level answer crops to eligible faculty members for blind independent evaluation, generates reference AI scores, detects evaluation discrepancies, provides moderation/review workflows, and tabulates final student marks.

---

## Architecture Overview

- **Backend:** FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic, PostgreSQL 16.
- **Computer Vision & OCR:** OpenCV, Tesseract OCR, PyPDFium2, synthetic sheet rendering utility.
- **AI Scoring & Moderation:** Semantic embeddings, heuristic keypoint rubrics, discrepancy detection engine.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Hook Form, Zod, Lucide.

---

## Local Development Quickstart

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- [Node.js](https://nodejs.org/) (v18+) & `npm`

### 2. Environment Configuration
Ensure your local `.env` file is present in the repository root (copied from `.env.example`):
```bash
cp .env.example .env
```
Inspect or customize the development seed passwords in `.env`:
```env
ADMIN_SEED_PASSWORD=Admin@123Password!
FACULTY_SEED_PASSWORD=Faculty@123Password!
REVIEWER_SEED_PASSWORD=Reviewer@123Password!
```

### 3. Start Backend & Database
Launch PostgreSQL and the FastAPI backend container:
```bash
docker compose up -d
```
Verify the backend is healthy:
- API Root: `http://localhost:8000/`
- Health check: `http://localhost:8000/health`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

### 4. Apply Database Migrations
Ensure PostgreSQL schema is at the latest migration revision (`008_final_scores`):
```bash
docker compose exec backend alembic upgrade head
```

### 5. Seed Development Accounts and Initial Academic Data
Populate the database with the required development accounts, a sample subject (CS304 Operating Systems), an examination, model questions with rubrics, and enrolled students:
```bash
docker compose exec backend python -m scripts.seed
```
*Optional:* Add `--sheets` to also generate synthetic handwritten sample answer sheets into `demo_sheets/` for upload testing:
```bash
docker compose exec backend python -m scripts.seed --sheets
```

### 6. Start the Frontend
In a separate terminal, install dependencies and start the Vite development server:
```bash
cd frontend
npm install
npm run dev
```
The application will be available at:
`http://localhost:5173`

---

## Development Accounts & Credentials

The seed command (`python -m scripts.seed`) creates the following local development accounts:

| Role | Email | Password Variable in `.env` | Default Dev Password |
|---|---|---|---|
| **Administrator** (`ADMIN`) | `admin@example.com` | `ADMIN_SEED_PASSWORD` | `Admin@123Password!` |
| **Faculty Member** (`FACULTY`) | `faculty1@example.com` | `FACULTY_SEED_PASSWORD` | `Faculty@123Password!` |
| **Faculty Member** (`FACULTY`) | `faculty2@example.com` | `FACULTY_SEED_PASSWORD` | `Faculty@123Password!` |
| **Faculty Member** (`FACULTY`) | `faculty3@example.com` | `FACULTY_SEED_PASSWORD` | `Faculty@123Password!` |
| **Reviewer** (`REVIEWER`) | `reviewer@example.com` | `REVIEWER_SEED_PASSWORD` | `Reviewer@123Password!` |

### Password Configuration & Safety Rules
1. **Environment-Driven:** Seed passwords are never hardcoded in source files. They are dynamically loaded from `ADMIN_SEED_PASSWORD`, `FACULTY_SEED_PASSWORD`, and `REVIEWER_SEED_PASSWORD` in `.env`.
2. **Safe & Idempotent:** If a user already exists in the database, the seed script preserves their existing password hash and will not overwrite or reset it.
3. **Customizing Passwords:** To use different passwords for local development, update the variables in `.env` *before* running `python -m scripts.seed`.
4. **Creating Additional Accounts:** Administrators can register new faculty and reviewers via the Admin UI or via `POST /api/auth/register`.
5. **Security Notice:** Never commit `.env` or production credentials to version control.

---

## Running Verification Tests

### Backend Test Suite (Pytest)
Run all 115 passing tests inside the Docker environment:
```bash
docker compose exec backend pytest -q
```

### Frontend Tests (Vitest)
Run the React test suite (unit and routing tests):
```bash
cd frontend
npm test
```

### Frontend Production Build
Validate TypeScript types and bundling:
```bash
cd frontend
npm run build
```

---

## Project Documentation

For in-depth architectural and product specifications:
- `AGENTS.md` — Agent instructions and source hierarchy.
- `PROJECT_KNOWLEDGE.md` — Product requirements, anti-anchoring rules, and workflows.
- `ARCHITECTURE.md` — Technical architecture, database schemas, and service boundaries.
- `DEVELOPMENT_RULES.md` — Engineering rules, security constraints, and testing protocols.
- `TASK_PLAN.md` — Specification implementation roadmap.
