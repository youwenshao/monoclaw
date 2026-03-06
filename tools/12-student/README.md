# Student Dashboard

Unified FastAPI application providing five productivity tools for Hong Kong university students, accessible at `http://mona.local:8507`.

## Tools

| Tool | Purpose |
|------|---------|
| **StudyBuddy** | RAG-powered Q&A from course materials (PDF, PPTX, DOCX), flashcards, summaries, and Anki export |
| **ExamGenerator** | Generate practice exams from past papers or content, auto-grading, discussion mode, and analytics |
| **ThesisFormatter** | Format theses per HKU, CUHK, HKUST, PolyU, CityU, HKBU, LingU, EdUHK guidelines |
| **InterviewPrep** | Coding practice with problem library, code runner, hints, mock interviews, and progress tracking |
| **JobTracker** | Job application kanban, parsing from job boards, interview reminders, and application tracking |

## Quick Start

### Prerequisites

- Python 3.11+
- ChromaDB (for StudyBuddy vector store)

### Installation

```bash
cd tools/12-student
pip install -e ../shared
pip install -e .
```

### Running the Dashboard

```bash
python -m student.app
```

Or with uvicorn:

```bash
uvicorn student.app:app --host 0.0.0.0 --port 8507
```

Then open **http://localhost:8507**. On first run, complete the setup wizard at `/setup/`.

## User Guide

### StudyBuddy

- **Ingestion** — Upload PDF, PPTX, DOCX; chunk and index into ChromaDB.
- **Q&A** — Ask questions; responses cite source chunks.
- **Flashcards** — Generate flashcards from content.
- **Summaries** — Generate section summaries and exam prep notes.
- **Anki Export** — Export flashcards for Anki.

### ExamGenerator

- **Generation** — Parse past papers or generate from content; distractor engine, Bloom taxonomy.
- **Exam Engine** — Timed practice with auto-save.
- **Grading** — Auto-grader, LLM grader, calculation grader, rubric-based feedback.
- **Discussion** — Post-exam discussion mode with follow-up questions.
- **Analytics** — Performance tracking, weakness analysis, trend reports.

### ThesisFormatter

- **Profiles** — HKU, CUHK, HKUST, PolyU, CityU, HKBU, LingU, EdUHK format profiles.
- **Formatting** — Margins, fonts, page numbering, TOC, list of figures/tables.
- **Bibliography** — BibTeX handling, citation inserter, APA and other styles.
- **Validation** — Format checker, completeness checker, report generator.

### InterviewPrep

- **Problem Library** — Curated coding problems with test cases.
- **Code Runner** — Execute code in sandbox (Python, JavaScript).
- **Hints** — Progressive hints and solution explainer.
- **Mock Interview** — Timed mock interview with multiple problems.
- **Progress** — Track solved problems, weaknesses, study plan.

### JobTracker

- **Kanban** — Stages: saved, applied, phone screen, assessment, interview, offer, accepted/rejected.
- **Parsing** — Extract job details from job board URLs.
- **Reminders** — Interview reminders (configurable hours before).
- **Tracking** — Application status and notes.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `chroma_collection_prefix` | ChromaDB collection prefix (default: `sb_`) |
| `extra` | `default_question_count` | ExamGenerator default question count |
| `extra` | `default_time_limit_minutes` | Exam time limit |
| `extra` | `supported_universities` | ThesisFormatter university list |
| `extra` | `kanban_stages` | JobTracker pipeline stages |
| `extra` | `code_execution_timeout_seconds` | InterviewPrep sandbox timeout |

## Architecture

```
tools/12-student/
├── config.yaml
├── student/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── dashboard/
│   ├── study_buddy/
│   ├── exam_generator/
│   ├── thesis_formatter/
│   ├── interview_prep/
│   └── job_tracker/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/student/`): `study_buddy.db`, `exam_generator.db`, `thesis_formatter.db`, `interview_prep.db`, `job_tracker.db`, `shared.db`, `mona_events.db`. **ChromaDB** at `~/OpenClawWorkspace/student/chroma_db/` for StudyBuddy.

## Running Tests

```bash
cd tools/12-student
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/student_tools_implementation_f13fccf3.plan.md`
- **Shared Library**: `tools/shared/`
