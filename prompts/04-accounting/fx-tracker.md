# FXTracker — Multi-Currency Transaction Logger & Reporter

## Overview

FXTracker automatically logs exchange rates from HKMA and market data sources, records multi-currency transactions, calculates realized and unrealized foreign exchange gains and losses, and generates FX reports for accounting compliance. It handles the currencies most common in HK business — USD, CNH, EUR, GBP, JPY — with awareness of the HKD-USD linked exchange rate system.

## Target User

Hong Kong accounting firms and CFOs of import/export businesses that hold multi-currency bank accounts and need accurate FX gain/loss calculations for financial reporting. Manual FX tracking in spreadsheets is error-prone and fails to capture daily rate movements, leading to inaccurate profit reporting and audit issues.

## Core Features

- **Automated Rate Fetching**: Pull daily exchange rates from HKMA's official API and supplement with Reuters/Bloomberg-compatible feeds. Store historical rates for lookback. Support spot rates, TT buying/selling rates, and note rates.
- **Transaction Logging**: Record foreign currency transactions (purchases, sales, payments, receipts) with date, amount, currency, and purpose. Auto-apply the day's exchange rate or accept a custom rate (e.g., actual bank conversion rate).
- **Realized FX Gain/Loss**: When a foreign currency receivable is settled or a payable is paid, calculate the realized FX gain/loss as the difference between the booking rate and settlement rate. Use FIFO, weighted average, or specific identification method (configurable).
- **Unrealized FX Gain/Loss**: At period end (month/quarter/year), revalue all outstanding foreign currency balances at the closing rate. Calculate unrealized FX gain/loss for financial statement disclosure. Generate a revaluation journal entry.
- **FX Exposure Report**: Show the firm's current foreign currency exposure by currency. Highlight large unhedged positions. Track exposure trends over time.
- **Compliance Reporting**: Generate FX reports formatted for Hong Kong Profits Tax computation (IRD requires FX gains to be included as assessable profits). Distinguish trading FX gains (taxable) from capital FX gains (non-taxable in HK).

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Rate fetching | `httpx` for HKMA API, `feedparser` for RSS |
| Data processing | `pandas`, `numpy` |
| Report generation | `reportlab` for PDF, `openpyxl` for Excel |
| Scheduling | `APScheduler` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Charts | `matplotlib` for exposure charts |
| Notifications | Twilio WhatsApp Business API |

## File Structure

```
/opt/openclaw/skills/local/fx-tracker/
├── main.py                  # FastAPI app + rate fetch scheduler
├── config.yaml              # Rate sources, currencies, alert thresholds
├── rates/
│   ├── fetcher.py           # Multi-source rate fetcher
│   ├── hkma.py              # HKMA exchange rate API client
│   └── cache.py             # Rate caching and interpolation
├── transactions/
│   ├── logger.py            # Transaction recording
│   ├── matcher.py           # Settlement matching (FIFO/avg)
│   └── revaluation.py       # Period-end revaluation engine
├── calculations/
│   ├── realized.py          # Realized FX gain/loss
│   ├── unrealized.py        # Unrealized FX gain/loss
│   └── exposure.py          # FX exposure calculator
├── reporting/
│   ├── fx_report.py         # Comprehensive FX report
│   ├── tax_schedule.py      # IRD-compliant FX schedule
│   ├── journal_entry.py     # Revaluation journal generator
│   └── charts.py            # Exposure visualization
├── dashboard/
│   ├── routes.py            # Web dashboard
│   └── templates/
│       ├── dashboard.html
│       ├── rates.html
│       └── exposure.html
└── tests/
    ├── test_rates.py
    ├── test_realized.py
    ├── test_unrealized.py
    └── test_reports.py

~/OpenClawWorkspace/fx-tracker/
├── fxtracker.db             # SQLite database
├── rate_history/            # Historical rate CSV backups
├── reports/                 # Generated FX reports
└── exports/                 # Journal entries for import
```

## Key Integrations

- **HKMA Exchange Rate API**: Primary source for official exchange rates. The HKMA publishes daily rates for major currencies against HKD. API endpoint: `https://api.hkma.gov.hk/public/market-data-and-statistics/daily-monetary-statistics/daily-figures-interbank-liquidity`.
- **ReconcileAgent (sibling tool)**: Share exchange rate data. Provide rate lookups for multi-currency transaction matching.
- **InvoiceOCR Pro (sibling tool)**: When invoices in foreign currencies are processed, auto-log the transaction with the day's rate.
- **Accounting Software**: Export revaluation journal entries as CSV/IIF for import into Xero, ABSS, or QuickBooks.
- **Twilio WhatsApp Business API**: Send daily rate summary and alert on significant rate movements.

## HK-Specific Requirements

- **Linked Exchange Rate System**: The HKD is pegged to USD within the band of 7.75-7.85 (Convertibility Undertaking). This means:
  - USD/HKD FX gains/losses are minimal for most transactions (typically <1.3% band)
  - The system should flag any USD/HKD rate outside the band as a data error
  - USD transactions can use a simplified rate (e.g., fixed 7.80) for internal management reporting, but must use actual rates for statutory reporting
- **CNH vs CNY Distinction**: Hong Kong uses the offshore renminbi (CNH), not the onshore rate (CNY). The two can diverge by 1-2%. Always use CNH for HK transactions. Label clearly in reports.
- **HKMA Rate Publication**: Rates published at approximately 11:30am HKT on business days. No rates on weekends and public holidays — use previous business day's rate.
- **Profits Tax Treatment**: Under HK Profits Tax:
  - FX gains/losses from revenue transactions (trade receivables/payables) are assessable/deductible
  - FX gains/losses from capital transactions (fixed assets, investments) are generally not taxable
  - The system must flag the nature of each FX gain/loss for tax computation
- **Common Currency Pairs**: In order of transaction volume for HK businesses: USD/HKD, CNH/HKD, EUR/HKD, GBP/HKD, JPY/HKD, SGD/HKD, AUD/HKD, CAD/HKD.
- **Revaluation Frequency**: Publicly listed companies revalue monthly. SMEs typically revalue at year-end only. Support both frequencies.
- **Accounting Standards**: HKFRS (Hong Kong Financial Reporting Standards) aligned with IFRS. IAS 21 governs foreign currency translation. FX differences on monetary items go to profit or loss.

## Data Model

```sql
CREATE TABLE exchange_rates (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    base_currency TEXT DEFAULT 'HKD',
    target_currency TEXT NOT NULL,
    buying_tt REAL,
    selling_tt REAL,
    mid_rate REAL NOT NULL,
    source TEXT DEFAULT 'HKMA',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, base_currency, target_currency, source)
);

CREATE TABLE fx_transactions (
    id INTEGER PRIMARY KEY,
    client_id INTEGER,
    transaction_date DATE NOT NULL,
    description TEXT,
    currency TEXT NOT NULL,
    foreign_amount REAL NOT NULL,
    exchange_rate REAL NOT NULL,
    hkd_amount REAL NOT NULL,
    transaction_type TEXT NOT NULL,
    nature TEXT DEFAULT 'revenue',
    reference TEXT,
    is_settled BOOLEAN DEFAULT FALSE,
    settled_date DATE,
    settlement_rate REAL,
    settlement_hkd REAL,
    realized_gain_loss REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE revaluations (
    id INTEGER PRIMARY KEY,
    client_id INTEGER,
    period_end_date DATE NOT NULL,
    currency TEXT NOT NULL,
    outstanding_foreign_amount REAL,
    original_hkd_amount REAL,
    closing_rate REAL,
    revalued_hkd_amount REAL,
    unrealized_gain_loss REAL,
    journal_entry_ref TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fx_exposure (
    id INTEGER PRIMARY KEY,
    client_id INTEGER,
    as_of_date DATE NOT NULL,
    currency TEXT NOT NULL,
    receivables_foreign REAL DEFAULT 0,
    payables_foreign REAL DEFAULT 0,
    net_exposure_foreign REAL,
    net_exposure_hkd REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rate_alerts (
    id INTEGER PRIMARY KEY,
    currency_pair TEXT NOT NULL,
    alert_type TEXT,
    threshold REAL,
    current_rate REAL,
    triggered_at TIMESTAMP,
    notified BOOLEAN DEFAULT FALSE
);
```

## Testing Criteria

- [ ] HKMA rate fetcher retrieves today's USD, CNH, EUR, GBP rates and stores correctly
- [ ] Weekends and public holidays correctly fall back to the previous business day's rate
- [ ] USD/HKD rate outside the 7.75-7.85 band is flagged as a potential data error
- [ ] Realized FX gain/loss calculation matches manual computation for 5 test cases (FIFO method)
- [ ] Unrealized FX revaluation at period end produces correct journal entries for a portfolio of 10 open positions
- [ ] FX exposure report correctly nets receivables and payables per currency
- [ ] Tax schedule distinguishes revenue vs capital FX gains for Profits Tax computation
- [ ] Daily rate summary WhatsApp message delivers by 12:00pm HKT

## Implementation Notes

- **No LLM required**: FX calculations are entirely mathematical. Memory footprint <200MB. Runs as a lightweight background service.
- **Rate fetching schedule**: Fetch HKMA rates at 12:00pm HKT daily (after publication). Retry at 12:30pm and 1:00pm if the first attempt fails. On weekends, skip. Store all historical rates — never overwrite.
- **FIFO implementation**: For realized gain/loss, maintain a queue of open positions per currency per client. When a settlement occurs, consume positions from the front of the queue. Calculate gain/loss per consumed lot, then sum.
- **Revaluation journal format**: Generate journal entries in the format: DR/CR Foreign Currency Translation Gain/Loss account, with the offsetting entry to the receivable/payable account. Include rate details in the memo field.
- **Rate interpolation**: If a rate is missing for a specific date (e.g., data gap), interpolate linearly from the nearest available dates. Flag interpolated rates in reports.
- **Privacy**: FX transaction data reveals business relationships and trade volumes. All data stays local. Reports shared only via secure channels.
- **Alerting**: Configurable rate alerts — e.g., notify if CNH/HKD moves more than 0.5% in a day. Useful for import/export businesses with large CNH exposure. Alert via WhatsApp.
