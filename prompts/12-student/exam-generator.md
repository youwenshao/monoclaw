# ExamGenerator — Practice Exam Creation and Grading System

## Overview

ExamGenerator creates practice exams from multiple sources — past exam papers, indexed course materials, and custom student requirements — across any university subject or discipline. It supports multiple question types (MCQ, short answer, long answer, calculation, true/false), provides a distraction-free exam-taking interface, and uses local LLM grading with detailed per-question feedback. After grading, students enter a Socratic discussion mode with Mona to learn from their mistakes. The tool integrates with StudyBuddy's ChromaDB index to generate questions grounded in actual course content.

## Target User

Hong Kong university students (undergraduate and postgraduate) across all disciplines — STEM, humanities, social sciences, business, law, languages — who want structured exam practice with AI-generated questions, automated grading, and personalized feedback to identify and address knowledge gaps before real exams.

## Core Features

- **Multi-Source Exam Generation**: Generate exams from three sources: (1) past exam papers uploaded as PDFs (OCR and parse into structured questions), (2) StudyBuddy's indexed course materials (LLM generates questions from content chunks), or (3) custom requirements specified by the student. Sources can be mixed within a single exam.
- **Flexible Question Types**: Multiple choice (4 options, 1 correct with plausible distractors), multiple select (4-6 options, 2+ correct), short answer (1-3 sentences), long answer / essay (paragraph-level, rubric-graded), calculation / problem-solving (step-by-step with partial credit), and true/false with justification.
- **Discipline-Agnostic Generation**: Question generation prompts adapt based on the course subject — STEM (formulas, calculations, diagrams), humanities (essay analysis, source interpretation), social sciences (case studies, theory application), languages (translation, grammar), business (case analysis, calculations), law (issue spotting, case application).
- **Bloom's Taxonomy Difficulty Control**: Student specifies difficulty distribution using Bloom's taxonomy levels (Remember, Understand, Apply, Analyze, Evaluate, Create) and difficulty tiers (easy, medium, hard). The generator distributes questions accordingly.
- **Exam-Taking Interface**: Distraction-free fullscreen exam view with question navigation sidebar, configurable timer (countdown/count-up/hidden), auto-save every 30 seconds, flag-for-review per question, and submit with confirmation dialog.
- **LLM-Powered Grading**: MCQ and true/false auto-graded instantly. Free-form answers graded by the local LLM against a rubric derived from source material, with partial credit and written justification. Calculation questions check both final answer and intermediate steps.
- **Post-Exam Discussion Mode**: After grading, a chat interface with Mona where the student can discuss any question. Mona has full context (questions, student answers, correct answers, rubric, source material) and uses Socratic method to guide understanding rather than just providing answers.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) for question generation, grading, and discussion |
| Vector DB | ChromaDB (shared with StudyBuddy) |
| Embeddings | `sentence-transformers` (multilingual, shared with StudyBuddy) |
| OCR | macOS Vision framework via `pyobjc-framework-Vision` for past paper parsing |
| PDF processing | `PyMuPDF` (fitz), `pdf2image` |
| Math rendering | `latex2sympy2` for LaTeX input parsing; MathJax (JS) for display |
| Database | `sqlite3` |
| UI | Streamlit with custom exam-taking components |
| Export | `openpyxl` for grade reports, `reportlab` for PDF exam printout |
| Scheduler | `APScheduler` for auto-save and timer management |
| Telegram | `python-telegram-bot` |
| WhatsApp | Twilio WhatsApp Business API |

## File Structure

```
/opt/openclaw/skills/local/exam-generator/
├── main.py                        # FastAPI + Streamlit entry point
├── config.yaml                    # Model paths, grading thresholds, default settings
├── generation/
│   ├── past_paper_parser.py       # OCR and parse past exam PDFs into structured questions
│   ├── content_generator.py       # Generate questions from StudyBuddy's indexed course materials
│   ├── custom_generator.py        # Generate questions from custom topic/chapter requirements
│   ├── distractor_engine.py       # Generate plausible MCQ distractors based on common misconceptions
│   ├── bloom_classifier.py        # Classify and target Bloom's taxonomy levels
│   └── subject_adapter.py         # Adapt generation prompts for STEM/humanities/social-sci/law/business/language
├── exam/
│   ├── exam_builder.py            # Assemble questions into an exam with ordering and point allocation
│   ├── exam_engine.py             # Exam session management (start, save, submit, timer)
│   └── answer_manager.py          # Track and persist student answers with auto-save
├── grading/
│   ├── auto_grader.py             # MCQ, true/false, and multi-select auto-grading
│   ├── llm_grader.py              # LLM-based grading for free-form answers with rubric
│   ├── calculation_grader.py      # Step-by-step calculation verification with partial credit
│   ├── rubric_generator.py        # Generate grading rubrics from source material
│   └── feedback_engine.py         # Per-question feedback with source citations
├── discussion/
│   ├── discussion_engine.py       # Post-exam Socratic discussion chat with Mona
│   ├── context_builder.py         # Build discussion context from exam, answers, and grading
│   └── followup_generator.py      # Generate follow-up questions on weak areas
├── analytics/
│   ├── performance_tracker.py     # Track scores across attempts, topics, and difficulty levels
│   ├── weakness_analyzer.py       # Identify weak topics from exam performance
│   └── trend_reporter.py          # Generate grade trend charts and improvement summaries
├── models/
│   ├── llm_handler.py             # MLX inference wrapper
│   └── prompts.py                 # All system prompts (generation, grading, discussion, rubric)
├── tests/
│   ├── test_generation.py
│   ├── test_grading.py
│   ├── test_discussion.py
│   └── test_past_paper.py
└── requirements.txt

~/OpenClawWorkspace/exam-generator/
├── examgenerator.db               # SQLite database
├── chroma_db/                     # Shared with StudyBuddy (symlink)
├── past_papers/                   # Uploaded past exam PDFs
├── generated_exams/               # Cached generated exam JSON files
├── exports/                       # Grade reports and exam printouts
└── discussion_logs/               # Saved post-exam discussion transcripts
```

## Key Integrations

- **StudyBuddy (sibling tool)**: Shares ChromaDB index and course organization. Questions are generated from the same indexed chunks that power StudyBuddy's Q&A. Exam performance data feeds into StudyBuddy's flashcard generation (weak areas get more flashcards).
- **ChromaDB**: Shared persistent vector store for course material retrieval during question generation and grading.
- **Local LLM (MLX)**: All question generation, grading, and discussion runs on-device. No exam content or student answers sent to external services.
- **Twilio WhatsApp Business API**: Send exam results summary and study reminders.
- **Telegram Bot API**: Secondary channel for exam reminders and grade notifications.

## GUI Specification

Part of the **Student Dashboard** (`http://mona.local:8507`) — ExamGenerator tab.

### Views

- **Exam Creation Wizard**:
  - Step 1 — **Source Selection**: Choose generation source (past paper upload, course materials, custom topics, or mixed). For past papers: drag-drop PDF upload with OCR progress. For course materials: select course and topic scope from StudyBuddy's index tree. For custom: enter topic keywords, chapter ranges, or paste specific requirements.
  - Step 2 — **Configuration**: Set question count, time limit (optional), difficulty distribution (sliders for easy/medium/hard), question type mix (checkboxes for MCQ/short/long/calculation/true-false), and Bloom's taxonomy targeting.
  - Step 3 — **Review & Generate**: Preview exam configuration summary. "Generate Exam" button with progress indicator. Preview generated questions with option to regenerate individual questions or the entire exam.

- **Exam-Taking Interface**:
  - Clean, distraction-free layout with optional fullscreen mode.
  - **Question Navigation Sidebar**: Numbered question list with status indicators — answered (green), unanswered (grey), flagged for review (amber). Click to jump to any question.
  - **Timer Display**: Configurable countdown, count-up, or hidden. Warning flash at 10 minutes and 2 minutes remaining.
  - **MCQ/Multi-Select**: Radio buttons or checkboxes with option text. Clear selection button.
  - **Short/Long Answer**: Rich text editor with basic formatting (bold, italic, bullet lists).
  - **Calculation**: Text input with LaTeX rendering preview for math expressions. Scratch pad area for intermediate steps.
  - **Flag for Review**: Toggle button per question. Flagged questions highlighted in the navigation sidebar.
  - **Auto-Save Indicator**: "Last saved: X seconds ago" status in the header.
  - **Submit Button**: Confirmation dialog showing answered/unanswered/flagged counts before final submission.

- **Grading & Feedback View**:
  - **Score Summary**: Overall percentage, points earned vs total, grade (A+/A/B+/B/C+/C/D/F), and comparison with past attempts.
  - **Topic Breakdown**: Bar chart showing score per topic area. Weak topics highlighted in red.
  - **Difficulty Breakdown**: Score by difficulty tier (easy/medium/hard) to identify if the student struggles with application vs recall.
  - **Per-Question Review**: Expandable cards for each question showing: question text, student's answer, correct answer, score, LLM feedback, and source material citation with page reference. Color-coded (green=correct, amber=partial, red=incorrect).
  - **Grade Trend Chart**: Line chart of scores across all exam attempts for the same course, showing improvement trajectory.

- **Discussion Mode**:
  - Chat interface with Mona, contextually aware of the completed exam.
  - **Question Selector**: Dropdown or click from the feedback view to focus discussion on a specific question.
  - **Mona's Approach**: Uses Socratic questioning — asks guiding questions rather than immediately giving answers. References source material. Generates follow-up practice questions on weak areas.
  - **Conversation History**: Full discussion saved and linked to the exam attempt. Reviewable later from the exam history.

- **Exam History**:
  - Table of all past exams with date, course, score, and time spent. Click to review grading, feedback, or resume a discussion.
  - Performance analytics: overall improvement trend, strongest/weakest topics, exam frequency.

### Mona Integration

- Mona generates exams based on student's specified requirements and presents them for review before the student begins.
- Mona grades all answers using the local LLM, providing detailed per-question feedback grounded in source material.
- In Discussion Mode, Mona uses Socratic method to guide the student through mistakes, referencing the course content.
- Mona identifies weak topics from exam performance and suggests targeted study sessions or generates follow-up mini-quizzes.
- Mona sends grade summaries and study reminders via WhatsApp/Telegram.

### Manual Mode

- Student can upload past papers for practice without Mona's AI generation — the parsed questions serve as a digital exam format.
- Student can manually take exams, review answers, and browse exam history without Mona's grading or discussion features (self-grading mode with answer key reveal).

## HK-Specific Requirements

- Bilingual support: Questions and answers in English or Traditional Chinese. Mixed-language exams common in HK universities (English questions, Chinese/English answers accepted).
- University exam formats: HK universities use specific exam formats — Section A (MCQ), Section B (short answer), Section C (essay/problem). The generator should support section-based exam structures.
- Common HK university subjects: Business (ACCT, FINA, MGMT, MKTG), Engineering (COMP, ELEC, MECH, CIVL), Science (PHYS, CHEM, BIOL, MATH), Humanities (HIST, PHIL, LING), Social Science (SOSC, PPOL, ECON), Law (LAWS). Course code format should be recognized.
- Academic integrity: Include a disclaimer that generated exams are for personal study use only. Generated questions should not replicate exact past exam questions verbatim — they should be variations and extensions.
- Grading scale: HK universities use letter grades with GPA equivalent. Display results using the common HK scale (A+ = 4.3, A = 4.0, A- = 3.7, B+ = 3.3, etc.).

## Data Model

```sql
CREATE TABLE exams (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    title TEXT,
    generation_source TEXT CHECK(generation_source IN ('past_paper','course_materials','custom','mixed')),
    scope_config TEXT,
    question_count INTEGER,
    time_limit_minutes INTEGER,
    status TEXT CHECK(status IN ('generating','ready','in_progress','completed','reviewed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE exam_questions (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER REFERENCES exams(id),
    question_index INTEGER,
    section TEXT,
    question_type TEXT CHECK(question_type IN ('mcq','multi_select','short_answer','long_answer','calculation','true_false')),
    question_text TEXT,
    options TEXT,
    correct_answer TEXT,
    rubric TEXT,
    source_chunks TEXT,
    difficulty TEXT CHECK(difficulty IN ('easy','medium','hard')),
    topic TEXT,
    points REAL DEFAULT 1.0,
    bloom_level TEXT CHECK(bloom_level IN ('remember','understand','apply','analyze','evaluate','create'))
);

CREATE TABLE exam_attempts (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER REFERENCES exams(id),
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    time_spent_seconds INTEGER,
    total_score REAL,
    max_score REAL,
    percentage REAL,
    letter_grade TEXT,
    topic_breakdown TEXT,
    difficulty_breakdown TEXT,
    feedback_summary TEXT,
    status TEXT CHECK(status IN ('in_progress','submitted','graded','reviewed'))
);

CREATE TABLE attempt_answers (
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER REFERENCES exam_attempts(id),
    question_id INTEGER REFERENCES exam_questions(id),
    student_answer TEXT,
    is_correct BOOLEAN,
    score REAL,
    max_score REAL,
    feedback TEXT,
    source_reference TEXT,
    flagged_for_review BOOLEAN DEFAULT FALSE,
    graded_at TIMESTAMP
);

CREATE TABLE exam_discussions (
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER REFERENCES exam_attempts(id),
    question_id INTEGER,
    role TEXT CHECK(role IN ('student','mona')),
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE past_papers (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    filename TEXT,
    file_path TEXT,
    parsed_questions INTEGER DEFAULT 0,
    academic_year TEXT,
    semester TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Student Profile**: Name, university, programme, year of study (shared with StudyBuddy if already configured)
2. **Course Library Link**: Connect to StudyBuddy's ChromaDB index — select which courses to enable for exam generation
3. **Past Paper Upload**: Optionally upload past exam papers for parsing (can be done later)
4. **Exam Preferences**: Default question count, time limit, preferred question types, and difficulty distribution
5. **Grading Scale**: Select university grading scale (HK standard A+ to F, or custom)
6. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token (for grade notifications and study reminders)
7. **Sample Exam**: Option to generate a sample exam from any indexed course to verify the system is working
8. **Connection Test**: Validates StudyBuddy index access, LLM model, and messaging APIs

## Testing Criteria

- [ ] Generates a 20-question MCQ exam from indexed course materials within 60 seconds
- [ ] Past paper OCR correctly parses questions, options, and point values from 5 sample PDF exam papers
- [ ] MCQ auto-grading returns correct scores for a test attempt with known answers
- [ ] LLM grading of a short answer question produces a reasonable score with written justification citing source material
- [ ] Calculation grading awards partial credit for correct methodology with wrong final answer
- [ ] Exam-taking interface auto-saves every 30 seconds and recovers state after page refresh
- [ ] Timer correctly counts down and triggers submission warning at 10-minute and 2-minute marks
- [ ] Discussion mode maintains context across 10+ message exchanges about a specific exam question
- [ ] Bloom's taxonomy distribution matches the requested difficulty configuration within ±10%
- [ ] Handles a Chinese-language course with Chinese questions and answers correctly
- [ ] Grade trend chart accurately shows improvement across 5+ exam attempts for the same course
- [ ] Question generation adapts appropriately between STEM (calculation-heavy) and humanities (essay-heavy) subjects

## Implementation Notes

- **Shared ChromaDB**: Symlink `~/OpenClawWorkspace/exam-generator/chroma_db/` to `~/OpenClawWorkspace/study-buddy/chroma_db/` to share the same index. Both tools can read; only StudyBuddy writes to the index.
- **Question generation pipeline**: Retrieve relevant chunks from ChromaDB for the specified topic/chapter → Pass to LLM with subject-adapted prompt → LLM generates question + answer + rubric → Validate question quality (no duplicate questions, proper formatting) → Store in database.
- **Distractor generation**: For MCQ, generate distractors by asking the LLM to produce common misconceptions for the correct answer. Validate that distractors are plausible but clearly wrong.
- **Rubric generation**: For free-form questions, auto-generate a rubric from the source material chunks. The rubric specifies key points worth specific marks. The LLM grader evaluates student answers against this rubric.
- **Past paper parsing**: Use macOS Vision OCR to extract text from scanned PDFs. Use LLM to parse the raw text into structured questions (detect question boundaries, options, point values). Store parsed questions as JSON for reuse.
- **Auto-save implementation**: Use Streamlit session state with periodic SQLite writes. On page refresh, load the last saved state. Include a "Resume Exam" option on the main page.
- **Discussion context window**: Build the discussion context from: exam question text + student answer + correct answer + rubric + grading feedback + relevant source chunks. Keep within 4K tokens to leave room for conversation history.
- **Memory budget**: LLM (~5GB) + ChromaDB (shared, ~2GB) + Streamlit app (~500MB) = ~7.5GB. Tight on 16GB M4 — advise closing other LLM-intensive tools during exam sessions.
- **Subject adaptation**: Maintain a set of subject-specific generation prompt templates. Detect subject from course code prefix (COMP=CS, ECON=economics, LAWS=law, etc.) or let the student specify manually. Each template adjusts question style, answer format, and grading criteria.
- **Exam integrity**: Hash each generated exam and store the hash. If a student re-generates from the same configuration, produce different questions (seeded randomization). Never generate the same exam twice.
- **Logging**: All operations logged to `/var/log/openclaw/exam-generator.log` with daily rotation (7-day retention). Student personal data and exam content masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Exam content (especially past papers) is copyrighted material — zero cloud processing. Past paper files stored locally only.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM model state, ChromaDB index status, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all exam data, attempts, grades, and discussion transcripts.
