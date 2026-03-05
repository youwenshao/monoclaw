# GrantTracker

## Tool Name & Overview

GrantTracker monitors research funding deadlines from Hong Kong's major grant bodies (RGC, ITF, NSFC), auto-populates common application form fields from researcher profiles, and tracks submission status through the review process. It serves as a centralized command center for academics managing multiple grant applications across different funding agencies with overlapping timelines.

## Target User

Hong Kong university researchers, principal investigators, and departmental research administrators who apply for competitive research funding and need to track multiple grant deadlines, prepare applications, and monitor submission outcomes.

## Core Features

- **Deadline Monitoring**: Scrapes and monitors RGC, ITF, NSFC, and other funding body websites for call-for-proposal deadlines; sends escalating reminders at 60, 30, 14, 7, and 3 days before each deadline
- **Form Auto-Population**: Pre-fills standard application fields (PI details, institutional affiliation, publication list, research track record) from a researcher profile, reducing repetitive data entry across multiple applications
- **Application Checklist**: Generates a submission checklist per grant scheme with all required documents, endorsement steps, and institutional deadlines (which are always earlier than the external deadline)
- **Submission Tracker**: Tracks application status from draft → internal review → submitted → under review → outcome; records reviewer comments and scores when available
- **Budget Template**: Pre-built budget templates for common HK grant schemes with correct budget categories (RA salary, equipment, travel, consumables) and current cost norms
- **Publication List Manager**: Maintains an up-to-date publication list formatted for each grant agency's requirements; auto-fetches citations from Google Scholar or Semantic Scholar

## Tech Stack

- **Web Scraping**: Playwright for monitoring RGC/ITF websites; BeautifulSoup4 for HTML parsing
- **Scheduler**: APScheduler for deadline reminders and periodic website checks
- **Notifications**: Twilio WhatsApp; smtplib for email reminders
- **Database**: SQLite for researcher profiles, grant applications, deadlines, and publication records
- **UI**: Streamlit dashboard with deadline calendar, application pipeline view, and budget editor
- **Document Generation**: python-docx for populating Word-based application forms; openpyxl for Excel budget templates

## File Structure

```
~/OpenClaw/tools/grant-tracker/
├── app.py                        # Streamlit grant management dashboard
├── monitoring/
│   ├── rgc_monitor.py            # RGC website scraper for deadlines
│   ├── itf_monitor.py            # ITF (Innovation and Technology Fund) scraper
│   ├── nsfc_monitor.py           # NSFC deadline tracking
│   └── deadline_aggregator.py    # Unified deadline calendar across agencies
├── applications/
│   ├── form_populator.py         # Auto-fill application form fields
│   ├── checklist_generator.py    # Submission checklist per scheme
│   ├── budget_builder.py         # Budget template population
│   └── submission_tracker.py     # Application lifecycle tracking
├── profile/
│   ├── researcher_profile.py     # PI profile management
│   ├── publication_manager.py    # Publication list maintenance
│   └── scholar_fetcher.py        # Google Scholar / Semantic Scholar data
├── notifications/
│   ├── reminder_engine.py        # Deadline reminder scheduling
│   ├── whatsapp.py               # Twilio WhatsApp alerts
│   └── email_sender.py           # Email notifications
├── data/
│   ├── grants.db                 # SQLite database
│   ├── budget_templates/         # Excel budget templates per scheme
│   └── grant_schemes.json        # Grant scheme definitions and deadlines
├── requirements.txt
└── README.md
```

## Key Integrations

- **RGC Website**: Scrapes Research Grants Council website for GRF, ECS, CRF, and other scheme deadlines
- **ITF Portal**: Monitors Innovation and Technology Fund for funding calls
- **Semantic Scholar / Google Scholar**: Fetches publication data for researcher profiles
- **Twilio WhatsApp / Email**: Multi-channel deadline reminders

## HK-Specific Requirements

- UGC/RGC scheme types: Tool must track deadlines and requirements for all major RGC schemes:
  - GRF (General Research Fund): Main competitive scheme, annual exercise, deadline typically November
  - ECS (Early Career Scheme): For junior researchers within 3 years of first academic appointment
  - CRF (Collaborative Research Fund): Group research projects, separate deadline from GRF
  - TRS (Theme-based Research Scheme): Large strategic research projects
  - RIF (Research Impact Fund): Impact-oriented research
  - HKPFS (Hong Kong PhD Fellowship Scheme): Doctoral student support
- ITF (Innovation and Technology Fund): Administered by ITC; different application process from RGC
- NSFC (National Natural Science Foundation of China): Many HK researchers apply for NSFC funding; deadlines follow Mainland academic calendar (typically March)
- Institutional deadlines: HK universities typically set internal deadlines 2-4 weeks before the external deadline for internal review — tool must track both
- RGC budget norms: RA (Research Assistant) salary scales follow UGC norms; equipment purchases >HK$200,000 need special justification; current postdoc salary norms ~HK$28,000-38,000/month
- RAE (Research Assessment Exercise): Publication records prepared for grant applications can also feed into the university's RAE submission
- Two-page research proposal format: GRF/ECS proposals have strict page limits — tool should warn when content approaches limits

## Data Model

```sql
CREATE TABLE researchers (
    id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    title TEXT,
    department TEXT,
    institution TEXT,
    email TEXT,
    orcid TEXT,
    google_scholar_id TEXT,
    research_interests TEXT,
    appointment_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE grant_schemes (
    id INTEGER PRIMARY KEY,
    agency TEXT CHECK(agency IN ('RGC','ITF','NSFC','Other')),
    scheme_name TEXT,
    scheme_code TEXT,
    description TEXT,
    typical_deadline_month INTEGER,
    typical_funding_range TEXT,
    duration_years INTEGER,
    eligibility_notes TEXT,
    url TEXT
);

CREATE TABLE deadlines (
    id INTEGER PRIMARY KEY,
    scheme_id INTEGER REFERENCES grant_schemes(id),
    year INTEGER,
    external_deadline DATE,
    institutional_deadline DATE,
    call_url TEXT,
    status TEXT CHECK(status IN ('upcoming','open','closed')) DEFAULT 'upcoming',
    notes TEXT
);

CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    researcher_id INTEGER REFERENCES researchers(id),
    scheme_id INTEGER REFERENCES grant_schemes(id),
    deadline_id INTEGER REFERENCES deadlines(id),
    project_title TEXT,
    requested_amount REAL,
    duration_months INTEGER,
    status TEXT CHECK(status IN ('planning','drafting','internal_review','submitted','under_review','awarded','rejected','withdrawn')) DEFAULT 'planning',
    submission_date DATE,
    outcome_date DATE,
    awarded_amount REAL,
    reviewer_score REAL,
    reviewer_comments TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE publications (
    id INTEGER PRIMARY KEY,
    researcher_id INTEGER REFERENCES researchers(id),
    title TEXT,
    authors TEXT,
    journal TEXT,
    year INTEGER,
    doi TEXT,
    citation_count INTEGER,
    is_corresponding_author BOOLEAN,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE budget_items (
    id INTEGER PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id),
    category TEXT CHECK(category IN ('ra_salary','postdoc_salary','equipment','travel','consumables','services','other')),
    description TEXT,
    year INTEGER,
    amount REAL,
    justification TEXT
);
```

## Testing Criteria

- [ ] Scrapes RGC website and correctly identifies current GRF/ECS deadline dates
- [ ] Sends a WhatsApp reminder 30 days before an upcoming GRF deadline
- [ ] Auto-populates PI name, department, institution, and publication count in an application form template
- [ ] Budget builder generates correct RA salary calculations using current UGC norms
- [ ] Submission tracker correctly transitions application from "submitted" to "under_review" to "awarded/rejected"
- [ ] Publication list exports in RGC-required format with correct author ordering
- [ ] Institutional deadline is set 3 weeks before external deadline by default

## Implementation Notes

- RGC website scraping: the RGC site structure changes infrequently; use Playwright to load the JavaScript-rendered deadlines page and extract dates
- Grant scheme definitions: maintain as a JSON file that is updated annually (new schemes are rare; deadlines shift by a few weeks each year)
- Publication fetching: use Semantic Scholar API (free, no key needed for basic usage) rather than Google Scholar (no official API, scraping is fragile)
- Budget templates: create Excel templates with formulas for automatic sub-totals per category per year; use openpyxl to populate researcher-specific values
- Institutional deadline offset: default to -21 days from external deadline; make configurable per institution
- Memory budget: ~2GB (web scraping + scheduling; no LLM needed for this tool — it's primarily a tracking and form-filling application)
- Consider adding a "success rate" tracker that helps researchers understand their historical success rate per scheme to guide future applications
- Data backup: grant application data represents significant researcher effort — implement automatic SQLite backup to a configurable location
