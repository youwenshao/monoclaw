# JobTracker

## Overview

JobTracker is a job search management tool that parses job descriptions from Hong Kong job platforms (CTgoodjobs, JobsDB, LinkedIn), matches job requirements against the student's CV keywords and skills, tracks application status through the hiring pipeline, and provides analytics on the student's job search progress. It centralizes the typically chaotic graduate job hunt into an organized, data-driven workflow.

## Target User

Hong Kong university students (final year and recent graduates), career changers, and job seekers who apply to multiple positions across HK job platforms and need to track applications, optimize their CV for specific roles, and manage interview schedules.

## Core Features

- **Job Description Parser**: Extracts structured information from job listings (role title, company, requirements, salary range, location, benefits) by URL or pasted text from CTgoodjobs, JobsDB, LinkedIn, and company career pages
- **CV Keyword Matching**: Compares job description requirements against the student's CV to produce a match score and identify missing keywords/skills that should be added for each application
- **Application Pipeline**: Kanban-style board tracking each application through stages: Saved → Applied → Phone Screen → Interview → Offer → Accepted/Rejected
- **Interview Scheduler**: Records upcoming interview dates, locations, and preparation notes; sends WhatsApp reminders 24 hours before each interview
- **Application Analytics**: Tracks response rate, time-to-response, conversion rates per stage, and application volume over time
- **Cover Letter Drafts**: Generates tailored cover letter drafts based on the job description and the student's CV using the local LLM

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Web Scraping | Playwright for parsing job listings from CTgoodjobs, JobsDB; httpx for LinkedIn API/scraping |
| LLM | MLX local inference (Qwen-2.5-7B) for keyword matching, cover letter generation, and job description analysis |
| NLP | rapidfuzz for skill matching; sentence-transformers for semantic similarity between CV and JD |
| Database | SQLite for job listings, applications, CV data, and analytics |
| UI | Streamlit with Kanban board, analytics dashboard, and CV review interface |
| Notifications | Twilio WhatsApp for interview reminders; APScheduler for scheduling |
| Charts | plotly for application funnel and response rate visualization |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/job-tracker/
├── app.py                        # Streamlit job search dashboard
├── parsing/
│   ├── ctgoodjobs_parser.py      # CTgoodjobs job listing scraper
│   ├── jobsdb_parser.py          # JobsDB listing scraper
│   ├── linkedin_parser.py        # LinkedIn job listing parser
│   ├── generic_parser.py         # Free-text job description parser
│   └── jd_structurer.py          # LLM-based JD field extraction
├── matching/
│   ├── cv_parser.py              # CV/resume keyword and skill extraction
│   ├── keyword_matcher.py        # JD vs CV keyword matching and scoring
│   └── gap_analyzer.py           # Identify missing skills/keywords
├── tracking/
│   ├── pipeline_manager.py       # Application stage tracking (Kanban)
│   ├── interview_scheduler.py    # Interview date and reminder management
│   └── analytics_engine.py       # Application statistics and conversion rates
├── generation/
│   ├── cover_letter.py           # Tailored cover letter generation
│   └── follow_up_drafter.py      # Post-interview follow-up email drafts
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # JD parsing, cover letter, and matching prompts
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/job-tracker/
├── jobtracker.db                 # SQLite database
└── cvs/                          # Uploaded CV/resume files
```

## Key Integrations

- **CTgoodjobs**: Hong Kong's leading local job platform — web scraping for job listings
- **JobsDB**: Major HK job search platform — listing parser and metadata extraction
- **LinkedIn**: Professional network job listings — parser with rate limiting
- **Twilio WhatsApp**: Interview reminders sent to the student's phone
- **Local LLM (MLX)**: JD analysis, cover letter generation, and keyword matching
- **Telegram Bot API**: Secondary channel for study reminders, interview notifications, and deadline alerts.

## GUI Specification

Part of the **Student Dashboard** (`http://mona.local:8507`) — JobTracker tab.

### Views

- **Kanban Board**: Drag-drop columns — Saved | Applied | Phone Screen | Assessment | Interview | Final Round | Offer | Accepted/Rejected. Job cards with company logo, title, and days-in-stage.
- **Job Detail Panel**: Parsed job description, match score gauge, missing keywords list, salary range, benefits summary, and deadline.
- **Cover Letter Editor**: AI-generated draft based on JD + CV with rich text editing. Side-by-side view with the job description.
- **Interview Calendar**: Upcoming interviews with date, type (phone/video/in-person/assessment centre), location, and preparation notes. WhatsApp reminders.
- **Analytics Dashboard**: Application funnel chart, response rate trend, time-to-response distribution, and applications per week.
- **CV Match View**: Upload CV, select a job listing, see keyword match percentage with specific gaps highlighted.

### Mona Integration

- Mona auto-parses job listings from CTgoodjobs and JobsDB URLs pasted into the tracker.
- Mona generates tailored cover letter drafts based on job requirements and the student's CV.
- Human manages the pipeline, edits cover letters, and prepares for interviews.

### Manual Mode

- Student can manually add jobs, manage the Kanban board, write cover letters, and track interviews without Mona.

## HK-Specific Requirements

- HK job platforms: CTgoodjobs (最受歡迎求職平台), JobsDB (by SEEK), LinkedIn, and company career pages are the main channels — prioritize CTgoodjobs and JobsDB parsing
- Common HK job categories: Finance/Banking, IT/Tech, Professional Services (Big 4), Trading, Retail/F&B, Government, Education — recognize these categories from JD parsing
- Salary format: HK jobs list salary as monthly (not annual) — typically "HK$15,000 - HK$25,000 per month"; parse and normalize to monthly HKD
- HK-specific benefits: Many JDs mention MPF, medical insurance, double pay (13th month), annual leave (>statutory 7 days), transportation allowance — extract and track these
- Bilingual JDs: Many HK job listings are bilingual (English + Chinese) or Chinese-only — parser must handle both
- Work visa awareness: For non-local students, flag job listings that specify "HK permanent resident only" or require employment visa sponsorship
- IANG (Immigration Arrangements for Non-local Graduates): Non-local graduates get a 2-year IANG visa — tool should note IANG eligibility timeline
- Graduate programme deadlines: Major HK employers (banks, Big 4, government) have annual graduate programme cycles with early deadlines (typically September-November for the following year) — calendar should pre-load these

## Data Model

```sql
CREATE TABLE job_listings (
    id INTEGER PRIMARY KEY,
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
    requirements TEXT,  -- JSON array of requirement strings
    skills_required TEXT,  -- JSON array of extracted skills
    benefits TEXT,
    description_raw TEXT,
    language TEXT,
    posted_date DATE,
    deadline DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cv_profiles (
    id INTEGER PRIMARY KEY,
    profile_name TEXT DEFAULT 'main',
    skills TEXT,  -- JSON array
    education TEXT,  -- JSON array
    experience TEXT,  -- JSON array
    keywords TEXT,  -- JSON array of extracted keywords
    file_path TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    job_id INTEGER REFERENCES job_listings(id),
    cv_profile_id INTEGER REFERENCES cv_profiles(id),
    match_score REAL,
    missing_keywords TEXT,  -- JSON array
    stage TEXT CHECK(stage IN ('saved','applied','phone_screen','assessment','interview','final_round','offer','accepted','rejected','withdrawn')) DEFAULT 'saved',
    applied_date DATE,
    response_date DATE,
    cover_letter TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE interviews (
    id INTEGER PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id),
    interview_type TEXT CHECK(interview_type IN ('phone','video','in_person','assessment_centre','group')),
    datetime TIMESTAMP,
    location TEXT,
    interviewer TEXT,
    preparation_notes TEXT,
    post_interview_notes TEXT,
    reminder_sent BOOLEAN DEFAULT FALSE
);

CREATE TABLE analytics_snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_date DATE,
    total_saved INTEGER,
    total_applied INTEGER,
    total_interviews INTEGER,
    total_offers INTEGER,
    response_rate REAL,
    avg_time_to_response_days REAL
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Student Profile**: Name, university, programme, year of study, expected graduation date
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token (for interview reminders and deadline alerts)
3. **CV Upload**: Upload current CV for job matching and cover letter generation
4. **Job Platform Preferences**: Select which platforms to track (CTgoodjobs, JobsDB, LinkedIn)
5. **Graduate Programme Calendar**: Pre-load HK graduate programme application deadlines
6. **Sample Data**: Option to seed demo job listings and sample applications for testing
7. **Connection Test**: Validates all API connections, Playwright browser, and LLM availability

## Testing Criteria

- [ ] Parses a CTgoodjobs listing URL and extracts title, company, salary range, and requirements correctly
- [ ] CV keyword matcher produces a match score >80% for a well-matched JD-CV pair
- [ ] Gap analyzer identifies 3 missing skills from a JD that aren't in the CV
- [ ] Kanban board correctly moves an application from "Applied" to "Interview" stage
- [ ] Cover letter generator produces a relevant, personalized draft referencing specific JD requirements
- [ ] Interview reminder fires via WhatsApp 24 hours before a scheduled interview
- [ ] Analytics dashboard shows correct response rate (applications with responses / total applications)

## Implementation Notes

- Job platform scraping: CTgoodjobs and JobsDB may require Playwright (JavaScript-rendered pages); implement respectful scraping with 2-3 second delays between requests
- LinkedIn parsing: avoid aggressive scraping (LinkedIn actively blocks); support manual paste of JD text as primary LinkedIn input method
- CV parsing: accept PDF or DOCX CV; use PyMuPDF/python-docx to extract text; use LLM to identify and extract skills, education, and experience sections
- Keyword matching: combine exact skill matching (from a normalized skill taxonomy) with semantic similarity (sentence-transformers) for a blended match score
- Cover letter generation: prompt the LLM with the JD requirements, CV highlights, and a cover letter template — produce a draft that the student must review and personalize
- Memory budget: ~5GB (LLM for analysis + Playwright for scraping + Streamlit dashboard)
- Application data privacy: job search data is personal — all data stays local in SQLite; never sync to external services
- Consider adding a "networking tracker" feature to log informational interviews, coffee chats, and referral contacts — networking is critical in HK's relationship-driven job market
- **Logging**: All operations logged to `/var/log/openclaw/job-tracker.log` with daily rotation (7-day retention). Student personal data and academic content masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Course materials (copyrighted textbooks, exam papers) processed locally only — zero cloud processing.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM/embedding model state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all study data, flashcards, job applications, and exam attempts.
