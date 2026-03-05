# SupplierLedger

## Tool Name & Overview

SupplierLedger is a payables and receivables tracking tool designed for Hong Kong small businesses that manage multiple supplier relationships. It tracks outstanding invoices, auto-sends monthly statements, generates aging reports, and provides cash flow forecasting based on expected payment timelines. It replaces the spreadsheet-based supplier tracking that most HK SMEs use, with automated reminders and reconciliation.

## Target User

Hong Kong small business owners, bookkeepers, and accounts payable/receivable clerks at SMEs who manage 10-100 supplier and customer relationships with manual invoice tracking and need better visibility into cash flow and outstanding balances.

## Core Features

- **Invoice Tracking**: Records payable and receivable invoices with amounts, due dates, payment terms, and partial payment tracking; supports PDF invoice attachment
- **Auto-Statement Generation**: Produces monthly statements per supplier/customer showing all transactions, payments received/made, and outstanding balance — auto-sends via email or WhatsApp
- **Aging Reports**: Generates aging analysis (current, 30, 60, 90+ days) for both payables and receivables with drill-down to individual invoices
- **Payment Reminders**: Sends automated payment reminders to customers with overdue invoices at configurable intervals (7 days, 14 days, 30 days past due)
- **Cash Flow Forecast**: Projects 30/60/90-day cash flow based on scheduled payables and expected receivables collections
- **Reconciliation Helper**: Matches bank statement entries to recorded invoices and payments; flags unmatched transactions for review

## Tech Stack

- **Database**: SQLite for invoices, payments, supplier/customer records, and transaction history
- **Document Generation**: reportlab for PDF statements and aging reports; openpyxl for Excel exports
- **Notifications**: Twilio WhatsApp for payment reminders and statement delivery; smtplib for email
- **LLM**: MLX local inference for parsing bank statements and matching transactions to invoices
- **UI**: Streamlit dashboard with ledger views, aging charts, and cash flow forecast
- **Charts**: plotly for aging distribution and cash flow visualization
- **Scheduler**: APScheduler for monthly statement generation and overdue payment reminders

## File Structure

```
~/OpenClaw/tools/supplier-ledger/
├── app.py                        # Streamlit ledger dashboard
├── ledger/
│   ├── invoice_manager.py        # Invoice CRUD with partial payment support
│   ├── payment_recorder.py       # Payment recording and allocation
│   ├── aging_engine.py           # Aging report calculation
│   └── reconciler.py             # Bank statement reconciliation
├── statements/
│   ├── statement_generator.py    # Monthly statement generation
│   ├── statement_sender.py       # Auto-send statements via WhatsApp/email
│   └── pdf_builder.py            # PDF statement formatting
├── forecasting/
│   ├── cash_flow.py              # Cash flow projection engine
│   └── collection_predictor.py   # Receivables collection likelihood estimation
├── reminders/
│   ├── overdue_alerter.py        # Overdue invoice detection and reminder sending
│   └── scheduler.py              # APScheduler for periodic tasks
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Bank statement parsing prompts
├── data/
│   ├── ledger.db                 # SQLite database
│   └── statement_templates/      # Statement PDF templates
├── requirements.txt
└── README.md
```

## Key Integrations

- **Twilio WhatsApp**: Payment reminders and monthly statement delivery to suppliers/customers
- **Email (SMTP)**: Backup channel for statement delivery and formal payment requests
- **Local LLM (MLX)**: Bank statement parsing and transaction matching
- **Bank Statement Import**: CSV/PDF import from major HK banks (HSBC, Hang Seng, Standard Chartered, BOC HK)

## HK-Specific Requirements

- HK payment terms: Common terms in HK business are 30-day, 60-day, and 90-day payment from invoice date; some industries (construction, F&B wholesale) use 90-120 day terms
- Payment methods: Track payments by method — cheque (still common in HK B2B), T/T (bank transfer), FPS, cash, Octopus — each has different clearing times
- Statement format: HK business statements typically show: opening balance, list of invoices, list of payments/credits, closing balance; dates in DD/MM/YYYY format
- Cheque handling: Despite digitization, post-dated cheques remain common in HK business — track cheque numbers and deposit dates
- HKD-centric: All amounts in HKD for domestic suppliers; support USD and CNH for cross-border supplier relationships
- Month-end processing: HK businesses typically process statements on calendar month-end; tool should auto-generate on the 1st of each month for the previous month
- Stamp duty on receipts: For receipts over HK$3, stamp duty of HK$3 applies (Stamp Duty Ordinance) — rarely enforced but the tool should note this
- Profits tax deductibility: Proper invoice records are essential for HK profits tax filing — the ledger serves as supporting documentation for IRD claims

## Data Model

```sql
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    contact_type TEXT CHECK(contact_type IN ('supplier','customer','both')),
    company_name TEXT NOT NULL,
    company_name_tc TEXT,
    contact_person TEXT,
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    address TEXT,
    payment_terms_days INTEGER DEFAULT 30,
    credit_limit REAL,
    br_number TEXT,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts(id),
    invoice_type TEXT CHECK(invoice_type IN ('payable','receivable')),
    invoice_number TEXT,
    invoice_date DATE,
    due_date DATE,
    currency TEXT DEFAULT 'HKD',
    total_amount REAL,
    paid_amount REAL DEFAULT 0,
    balance REAL,
    status TEXT CHECK(status IN ('draft','outstanding','partially_paid','paid','overdue','disputed','written_off')) DEFAULT 'outstanding',
    pdf_path TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id),
    payment_date DATE,
    amount REAL,
    payment_method TEXT CHECK(payment_method IN ('cheque','bank_transfer','fps','cash','octopus','other')),
    cheque_number TEXT,
    bank_reference TEXT,
    notes TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE statements (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts(id),
    statement_date DATE,
    opening_balance REAL,
    closing_balance REAL,
    pdf_path TEXT,
    sent_via TEXT,
    sent_at TIMESTAMP,
    status TEXT DEFAULT 'generated'
);

CREATE TABLE bank_transactions (
    id INTEGER PRIMARY KEY,
    transaction_date DATE,
    description TEXT,
    amount REAL,
    bank_name TEXT,
    matched_invoice_id INTEGER REFERENCES invoices(id),
    match_status TEXT CHECK(match_status IN ('matched','unmatched','manual')) DEFAULT 'unmatched',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Creates a payable invoice with 60-day terms and correctly calculates due date
- [ ] Records a partial payment and updates invoice balance and status to "partially_paid"
- [ ] Aging report correctly buckets invoices into current/30/60/90+ day categories
- [ ] Monthly statement generates with correct opening balance, transactions, and closing balance
- [ ] Payment reminder sends via WhatsApp at 7 days past due with correct invoice details
- [ ] Cash flow forecast shows expected outflows/inflows for the next 30 days based on outstanding invoices
- [ ] Bank statement reconciliation matches a bank transfer to the correct invoice by amount and reference

## Implementation Notes

- Invoice balance tracking: use a trigger or computed field to always maintain `balance = total_amount - paid_amount`; recalculate on every payment recording
- Aging calculation: compute aging from invoice due date (not invoice date) — this is the standard HK business convention
- Statement generation: run as a scheduled job on the 1st of each month; generate PDF, store locally, then send via configured channel
- Bank statement import: support CSV export format from HSBC (most common HK business bank); parse the specific column layout used by HSBC business banking
- Reconciliation: match by exact amount first, then by amount + date range (±3 days); use LLM for parsing transaction descriptions when reference numbers are missing
- Cash flow forecast: simple model — sum expected collections by week (based on customer payment history) and committed payables by due date
- Memory budget: ~3GB (LLM only needed for bank statement parsing; core ledger operations are pure computation)
- Data backup: financial records are critical — implement automatic daily SQLite backup with 30-day retention
- Consider adding support for recurring invoices (e.g., monthly rent payable) that auto-generate each month
