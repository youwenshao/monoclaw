"""Database schema initialization for all student tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# StudyBuddy
# ---------------------------------------------------------------------------
STUDY_BUDDY_SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT,
    course_name TEXT,
    semester TEXT,
    instructor TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id),
    filename TEXT,
    file_path TEXT,
    doc_type TEXT CHECK(doc_type IN ('pdf','pptx','docx','txt','md')),
    title TEXT,
    page_count INTEGER,
    chunk_count INTEGER,
    language TEXT,
    indexed BOOLEAN DEFAULT FALSE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id),
    chunk_index INTEGER,
    text_content TEXT,
    page_number INTEGER,
    section_title TEXT,
    chroma_id TEXT
);

CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT,
    course_id INTEGER,
    answer_text TEXT,
    cited_chunks TEXT,
    helpful BOOLEAN,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flashcards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id),
    document_id INTEGER REFERENCES documents(id),
    question TEXT,
    answer TEXT,
    difficulty TEXT CHECK(difficulty IN ('easy','medium','hard')) DEFAULT 'medium',
    review_count INTEGER DEFAULT 0,
    last_reviewed TIMESTAMP,
    next_review TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# ExamGenerator
# ---------------------------------------------------------------------------
EXAM_GENERATOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    title TEXT,
    generation_source TEXT CHECK(generation_source IN ('past_paper','course_materials','custom','mixed')),
    scope_config TEXT,
    question_count INTEGER,
    time_limit_minutes INTEGER,
    status TEXT CHECK(status IN ('generating','ready','in_progress','completed','reviewed')) DEFAULT 'generating',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE TABLE IF NOT EXISTS exam_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    status TEXT CHECK(status IN ('in_progress','submitted','graded','reviewed')) DEFAULT 'in_progress'
);

CREATE TABLE IF NOT EXISTS attempt_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE TABLE IF NOT EXISTS exam_discussions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER REFERENCES exam_attempts(id),
    question_id INTEGER,
    role TEXT CHECK(role IN ('student','mona')),
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS past_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    filename TEXT,
    file_path TEXT,
    parsed_questions INTEGER DEFAULT 0,
    academic_year TEXT,
    semester TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# ThesisFormatter
# ---------------------------------------------------------------------------
THESIS_FORMATTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS formatting_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university TEXT NOT NULL,
    degree_level TEXT CHECK(degree_level IN ('undergraduate','mphil','phd')),
    font_name TEXT DEFAULT 'Times New Roman',
    font_size INTEGER DEFAULT 12,
    line_spacing REAL DEFAULT 1.5,
    margin_top REAL DEFAULT 25,
    margin_bottom REAL DEFAULT 25,
    margin_left REAL DEFAULT 25,
    margin_right REAL DEFAULT 25,
    page_size TEXT DEFAULT 'A4',
    front_matter_numbering TEXT DEFAULT 'roman',
    main_body_numbering TEXT DEFAULT 'arabic',
    required_sections TEXT,
    heading_styles TEXT,
    notes TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS thesis_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    author TEXT,
    university TEXT,
    department TEXT,
    degree TEXT,
    supervisor TEXT,
    year INTEGER,
    profile_id INTEGER REFERENCES formatting_profiles(id),
    source_file TEXT,
    formatted_file TEXT,
    validation_status TEXT DEFAULT 'not_validated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES thesis_projects(id),
    check_type TEXT,
    passed BOOLEAN,
    message TEXT,
    location TEXT,
    severity TEXT CHECK(severity IN ('error','warning','info')),
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES thesis_projects(id),
    section_type TEXT CHECK(section_type IN ('cover','title','declaration','abstract_en','abstract_tc','acknowledgments','toc','lof','lot','chapter','appendix','bibliography')),
    section_title TEXT,
    page_start INTEGER,
    page_end INTEGER,
    status TEXT DEFAULT 'detected'
);
"""

# ---------------------------------------------------------------------------
# InterviewPrep
# ---------------------------------------------------------------------------
INTERVIEW_PREP_SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    slug TEXT UNIQUE,
    description TEXT,
    difficulty TEXT CHECK(difficulty IN ('easy','medium','hard')),
    topic TEXT,
    subtopic TEXT,
    example_input TEXT,
    example_output TEXT,
    constraints TEXT,
    optimal_time_complexity TEXT,
    optimal_space_complexity TEXT,
    solution_python TEXT,
    solution_javascript TEXT,
    hints TEXT,
    test_cases TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER REFERENCES problems(id),
    code TEXT,
    language TEXT CHECK(language IN ('python','javascript')),
    passed_tests INTEGER,
    total_tests INTEGER,
    is_correct BOOLEAN,
    hints_used INTEGER DEFAULT 0,
    time_spent_seconds INTEGER,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    problems_attempted INTEGER DEFAULT 0,
    problems_solved INTEGER DEFAULT 0,
    avg_time_seconds REAL,
    avg_hints_used REAL,
    solve_rate REAL,
    last_practiced TIMESTAMP,
    strength_level TEXT CHECK(strength_level IN ('weak','developing','strong')) DEFAULT 'weak'
);

CREATE TABLE IF NOT EXISTS mock_interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    problems TEXT,
    results TEXT,
    overall_score REAL,
    feedback TEXT
);

CREATE TABLE IF NOT EXISTS study_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    focus_topics TEXT,
    daily_problems INTEGER DEFAULT 3,
    duration_days INTEGER DEFAULT 14,
    plan_details TEXT
);
"""

# ---------------------------------------------------------------------------
# JobTracker
# ---------------------------------------------------------------------------
JOB_TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT CHECK(source IN ('ctgoodjobs','jobsdb','linkedin','company_site','other')),
    url TEXT,
    title TEXT,
    company TEXT,
    location TEXT,
    district TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_period TEXT DEFAULT 'monthly',
    job_type TEXT CHECK(job_type IN ('full_time','part_time','contract','internship','graduate_programme')),
    industry TEXT,
    requirements TEXT,
    skills_required TEXT,
    benefits TEXT,
    description_raw TEXT,
    language TEXT,
    posted_date DATE,
    deadline DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cv_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT DEFAULT 'main',
    skills TEXT,
    education TEXT,
    experience TEXT,
    keywords TEXT,
    file_path TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES job_listings(id),
    cv_profile_id INTEGER REFERENCES cv_profiles(id),
    match_score REAL,
    missing_keywords TEXT,
    stage TEXT CHECK(stage IN ('saved','applied','phone_screen','assessment','interview','final_round','offer','accepted','rejected','withdrawn')) DEFAULT 'saved',
    applied_date DATE,
    response_date DATE,
    cover_letter TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id),
    interview_type TEXT CHECK(interview_type IN ('phone','video','in_person','assessment_centre','group')),
    datetime TIMESTAMP,
    location TEXT,
    interviewer TEXT,
    preparation_notes TEXT,
    post_interview_notes TEXT,
    reminder_sent BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE,
    total_saved INTEGER,
    total_applied INTEGER,
    total_interviews INTEGER,
    total_offers INTEGER,
    response_rate REAL,
    avg_time_to_response_days REAL
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    university TEXT,
    programme TEXT,
    year_of_study TEXT,
    expected_graduation TEXT,
    email TEXT,
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/student") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/student") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "study_buddy": db_dir / "study_buddy.db",
        "exam_generator": db_dir / "exam_generator.db",
        "thesis_formatter": db_dir / "thesis_formatter.db",
        "interview_prep": db_dir / "interview_prep.db",
        "job_tracker": db_dir / "job_tracker.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["study_buddy"], STUDY_BUDDY_SCHEMA)
    run_migrations(db_paths["exam_generator"], EXAM_GENERATOR_SCHEMA)
    run_migrations(db_paths["thesis_formatter"], THESIS_FORMATTER_SCHEMA)
    run_migrations(db_paths["interview_prep"], INTERVIEW_PREP_SCHEMA)
    run_migrations(db_paths["job_tracker"], JOB_TRACKER_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
