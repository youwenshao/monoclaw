# MPFCalc

## Overview

MPFCalc automates the calculation of Mandatory Provident Fund (MPF) contributions for Hong Kong small business employers. It computes the mandatory 5% employer and employee contributions (subject to the HK$1,500 monthly cap and HK$7,100 minimum relevant income threshold), generates remittance statements for MPF trustees, handles voluntary contributions, and tracks contribution history for compliance reporting. Eliminates the manual spreadsheet calculations that most small HK businesses perform monthly.

## Target User

Hong Kong small business owners, sole proprietors, and HR/payroll administrators at SMEs (1-50 employees) who manually calculate monthly MPF contributions and prepare trustee remittance statements.

## Core Features

- **Automatic MPF Calculation**: Computes mandatory contributions for all employees based on relevant income — handles the minimum income level (HK$7,100), maximum relevant income level (HK$30,000), and the 5% contribution rate with HK$1,500 cap
- **Employee Classification**: Distinguishes between full-time, part-time, and casual employees for contribution calculation; handles the 60-day employment rule for new employees
- **Remittance Statement Generator**: Produces formatted remittance statements compatible with major MPF trustees (HSBC Provident Fund Trustee, AIA, Manulife, Sun Life, BCT)
- **Voluntary Contribution Tracking**: Records and tracks employer and employee voluntary contributions (TVC — Tax Deductible Voluntary Contributions up to HK$60,000/year)
- **Compliance Dashboard**: Monitors contribution deadlines (contribution day: on or before the 10th of the following month), flags late contributions, and generates MPFA compliance records
- **Annual Summary**: Produces employee-level annual MPF contribution summaries for tax filing (Employer's Return BIR56A/IR56B)

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Calculation Engine | Python decimal module for precise monetary calculations (no floating-point errors) |
| Document Generation | openpyxl for Excel remittance statements; reportlab for PDF contribution summaries |
| Database | SQLite for employee records, monthly contributions, and compliance history |
| UI | Streamlit dashboard with monthly payroll view and compliance status |
| Scheduler | APScheduler for monthly contribution reminders (5 days before contribution day) |
| Notifications | Twilio WhatsApp/SMTP email for deadline reminders |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/mpf-calc/
├── app.py                        # Streamlit MPF dashboard
├── calculation/
│   ├── mpf_engine.py             # Core MPF contribution calculation
│   ├── income_rules.py           # Relevant income classification and thresholds
│   ├── employee_classifier.py    # Full-time/part-time/casual classification
│   └── voluntary_contrib.py      # TVC and other voluntary contribution tracking
├── reporting/
│   ├── remittance_generator.py   # Trustee remittance statement generation
│   ├── annual_summary.py         # Annual contribution summary (IR56B support)
│   ├── compliance_report.py      # MPFA compliance record generation
│   └── pdf_export.py             # PDF report generation
├── payroll/
│   ├── employee_manager.py       # Employee CRUD and income recording
│   └── payroll_processor.py      # Monthly payroll processing with MPF deduction
├── notifications/
│   ├── reminder_engine.py        # Monthly contribution deadline reminders
│   └── whatsapp.py               # Twilio WhatsApp alerts
├── data/
│   ├── mpf.db                    # SQLite database
│   └── trustee_templates/        # Remittance statement templates per trustee
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/mpf-calc/
├── mpf.db                            # SQLite database (employees, contributions, payroll)
├── remittance_reports/               # Generated remittance statements
├── annual_summaries/                 # Annual contribution summaries for tax filing
└── exports/                          # Excel and PDF exports
```

## Key Integrations

- **MPF Trustee Portals**: Generates remittance statements in formats compatible with major HK MPF trustees
- **Twilio WhatsApp**: Monthly contribution deadline reminders to the business owner
- **IRD Tax Filing**: Annual contribution summaries formatted for inclusion in BIR56A/IR56B employer's returns
- **Telegram Bot API**: Secondary channel for business alerts, customer communication, and payment reminders.

## GUI Specification

Part of the **Solopreneur Dashboard** (`http://mona.local:8506`) — MPFCalc tab.

### Views

- **Employee Table**: All employees with name, classification (full-time/part-time/casual), monthly salary, MPF enrollment date, and 60-day rule status.
- **Monthly Calculator**: Auto-calculated mandatory contributions for each employee. Editable overrides for variable income components (overtime, commission, bonus). Clear breakdown of employer vs employee portions.
- **Remittance Statement Preview**: Formatted statement matching the selected MPF trustee's template. PDF download button.
- **Compliance Dashboard**: Contribution day countdown timer. Late payment warnings with 5% surcharge calculation. Historical compliance record.
- **What-If Calculator**: Enter a proposed salary for a new hire → instantly see total employer cost including MPF contribution.
- **Annual Summary**: Employee-level annual contribution totals formatted for IR56B employer's return filing.

### Mona Integration

- Mona auto-calculates monthly contributions when payroll data is entered or updated.
- Mona sends contribution deadline reminders via WhatsApp 5 days before the contribution day.
- Human reviews calculations, generates remittance statements, and handles exceptions.

### Manual Mode

- Business owner can manually enter employee data, calculate contributions, generate statements, and track compliance without Mona.

## HK-Specific Requirements

- MPFO (Mandatory Provident Fund Schemes Ordinance, Cap 485): Governs the entire MPF system — tool must implement rules precisely:
  - Mandatory contribution rate: 5% of relevant income for both employer and employee
  - Maximum relevant income: HK$30,000/month → maximum contribution HK$1,500/month each
  - Minimum relevant income: HK$7,100/month → employee is exempt from contributing but employer must still contribute 5%
  - Below minimum: if relevant income < HK$7,100, employee contribution = $0, employer contribution = 5% of actual income
- 60-day employment rule: No MPF contributions required during the first 60 days of employment; employer must enroll employee within 60 days
- Contribution day: Employer must pay contributions to the trustee on or before the contribution day (10th of the month following the wage period); late contributions incur a 5% surcharge
- Relevant income definition: Includes wages, salary, leave pay, overtime pay, commissions, bonuses; excludes severance/long service payments, Housing Allowance (if non-cash)
- Self-employed persons: Different contribution rules (contribute on annual income basis, quarterly or annually)
- Tax Deductible Voluntary Contributions (TVC): Introduced in April 2019, capped at HK$60,000/year for tax deduction purposes
- Major MPF trustees in HK: HSBC Provident Fund Trustee, AIA Company (Trustee), Manulife (Int'l), Sun Life Hong Kong, BCT Group, BOCI-Prudential — each has slightly different remittance formats

## Data Model

```sql
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    hkid_last4 TEXT,
    employment_type TEXT CHECK(employment_type IN ('full_time','part_time','casual')),
    start_date DATE,
    mpf_enrollment_date DATE,
    mpf_scheme TEXT,
    mpf_member_number TEXT,
    monthly_salary REAL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE monthly_contributions (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    contribution_month DATE,  -- first day of the month
    relevant_income REAL,
    employer_mandatory REAL,
    employee_mandatory REAL,
    employer_voluntary REAL DEFAULT 0,
    employee_voluntary REAL DEFAULT 0,
    total_contribution REAL,
    payment_status TEXT CHECK(payment_status IN ('calculated','pending','paid','late')) DEFAULT 'calculated',
    payment_date DATE,
    surcharge REAL DEFAULT 0,
    notes TEXT
);

CREATE TABLE payroll_records (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    pay_period_start DATE,
    pay_period_end DATE,
    basic_salary REAL,
    overtime REAL DEFAULT 0,
    commission REAL DEFAULT 0,
    bonus REAL DEFAULT 0,
    other_income REAL DEFAULT 0,
    total_relevant_income REAL,
    mpf_employee_deduction REAL,
    net_pay REAL
);

CREATE TABLE remittance_submissions (
    id INTEGER PRIMARY KEY,
    contribution_month DATE,
    trustee TEXT,
    total_employer REAL,
    total_employee REAL,
    total_amount REAL,
    employee_count INTEGER,
    submitted_date DATE,
    reference_number TEXT,
    status TEXT CHECK(status IN ('draft','submitted','confirmed')) DEFAULT 'draft'
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Business Profile**: Business name, BR number, business type, operating hours, base currency (HKD)
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
3. **MPF Trustee**: Select MPF trustee, configure contribution day, upload remittance statement template
4. **Employee Import**: Import employee list from CSV/Excel or enter manually; classify employment types (full-time/part-time/casual) and set start dates
5. **Payroll Configuration**: Define income components (basic salary, overtime, commission, bonus) per employee
6. **Sample Data**: Option to seed demo employees and contribution history for testing
7. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] Correctly calculates 5% employer and employee contributions for income of HK$25,000 (result: HK$1,250 each)
- [ ] Caps employee contribution at HK$1,500 for income of HK$35,000 (above maximum relevant income)
- [ ] Exempts employee contribution for income of HK$6,000 (below minimum) while still calculating employer's 5% (HK$300)
- [ ] Handles the 60-day rule: no contributions calculated for first 60 days of a new employee
- [ ] Remittance statement generates correctly for HSBC Provident Fund format with all employee contributions listed
- [ ] Late contribution surcharge (5%) calculated when payment date exceeds contribution day
- [ ] Annual summary matches the format needed for IR56B employer's return filing

## Implementation Notes

- Use Python's `decimal.Decimal` for all monetary calculations to avoid floating-point rounding errors — MPF calculations are audited and must be exact to the cent
- Contribution month handling: contributions for wages in month M are due by the 10th of month M+1 — the tool must correctly map payroll periods to contribution periods
- Remittance statement formats: each trustee has a slightly different Excel template — maintain a template per trustee and populate using openpyxl
- New employee handling: auto-calculate the 60-day window from start_date; automatically begin contributions from the appropriate month
- Income components: create a flexible income component system so business owners can add/remove income types (overtime, commission, allowances) per their payroll structure
- Memory budget: ~1GB (this is a computation-heavy, LLM-light tool; no inference needed for core calculations)
- Data security: MPF data includes employee financial information — implement SQLite encryption (sqlcipher) or at minimum restrict file permissions
- Consider adding a "what-if" calculator for new hires — enter proposed salary and see the employer's total cost including MPF contribution
- **Logging**: All operations logged to `/var/log/openclaw/mpf-calc.log` with daily rotation (7-day retention). Financial data and customer details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Business financial data protected under PDPO — zero cloud processing for transaction data.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, POS sync status, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all business data for backup or accountant handoff.
