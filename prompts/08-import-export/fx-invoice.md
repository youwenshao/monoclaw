# FXInvoice

## Tool Name & Overview

FXInvoice is a multi-currency invoice generator with integrated FX rate tracking and basic hedging suggestions for Hong Kong trade businesses. It creates professional invoices in USD, CNH (offshore RMB), HKD, EUR, and other currencies, auto-converts between currencies at real-time or locked-in rates, and tracks payment status across multiple currencies. Designed for the multi-currency reality of Hong Kong's international trade hub.

## Target User

Hong Kong import-export traders, trading company accountants, and finance managers who issue and receive invoices in multiple currencies and need to manage FX exposure, track cross-currency payments, and maintain accurate multi-currency books.

## Core Features

- **Multi-Currency Invoice Generation**: Creates professional invoices in any currency with automatic conversion to HKD equivalent; supports dual-currency display (e.g., USD amount with HKD equivalent)
- **Real-Time FX Rates**: Fetches live exchange rates from HKMA, ECB, or open FX APIs; allows rate locking at invoice creation for consistent pricing
- **FX Hedging Suggestions**: For large invoices with extended payment terms, suggests simple hedging strategies (forward contract, spot conversion timing) based on historical rate trends
- **Payment Tracking**: Multi-currency payment ledger tracking partial payments, overpayments, and FX gains/losses on settlement
- **Statement Generation**: Produces monthly statements per customer/supplier showing outstanding balances in original and HKD-equivalent currencies
- **Aging Reports**: Multi-currency aging reports (current, 30, 60, 90+ days) with HKD normalization for total exposure calculation

## Tech Stack

- **FX Data**: httpx for fetching rates from exchangerate-api.com, HKMA API, or ECB reference rates
- **Invoice Generation**: reportlab for PDF invoices; openpyxl for Excel format; Jinja2 for HTML invoice templates
- **Database**: SQLite for invoices, payments, FX rate history, customer/supplier records
- **UI**: Streamlit dashboard with FX rate charts, invoice management, and payment tracking
- **Charts**: plotly for FX rate trend visualization and exposure analytics
- **LLM**: MLX local inference for payment advice parsing and bank statement reconciliation assistance

## File Structure

```
~/OpenClaw/tools/fx-invoice/
├── app.py                        # Streamlit finance dashboard
├── invoicing/
│   ├── invoice_generator.py      # Multi-currency invoice creation
│   ├── statement_generator.py    # Monthly statement production
│   ├── template_engine.py        # Jinja2 invoice template rendering
│   └── pdf_export.py             # PDF invoice generation
├── fx/
│   ├── rate_fetcher.py           # Live FX rate retrieval from multiple sources
│   ├── rate_cache.py             # Rate caching and historical storage
│   ├── converter.py              # Currency conversion engine
│   └── hedging_advisor.py        # Basic FX hedging suggestions
├── payments/
│   ├── payment_tracker.py        # Multi-currency payment recording
│   ├── reconciler.py             # Bank statement reconciliation
│   └── aging_report.py           # Aged receivables/payables reports
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Payment parsing prompts
├── data/
│   ├── fx_invoice.db             # SQLite database
│   └── invoice_templates/        # Jinja2 HTML invoice templates
├── requirements.txt
└── README.md
```

## Key Integrations

- **HKMA Exchange Rate API**: Official HKD exchange rates published by the Hong Kong Monetary Authority
- **Exchange Rate API / ECB**: Broader currency pair coverage for non-HKD conversions
- **Local LLM (MLX)**: Assists with bank statement parsing and unstructured payment advice interpretation
- **PDF Generation**: Professional invoice output suitable for sending to international trade partners

## HK-Specific Requirements

- HKD peg: HKD is pegged to USD at 7.75-7.85 (Linked Exchange Rate System) — tool should flag when USD/HKD rate approaches the band edges
- RTGS/CHATS: Hong Kong's interbank payment systems — RTGS for HKD, USD CHATS for USD, EUR CHATS for EUR, RMB CHATS for CNH — tool should reference the appropriate system for each currency
- CNH (offshore RMB): Hong Kong is the largest offshore RMB centre; CNH rate can differ from onshore CNY — tool must clearly distinguish CNH from CNY
- Trade finance instruments: Common HK payment methods include T/T (telegraphic transfer), L/C (letter of credit), D/P (documents against payment), D/A (documents against acceptance) — invoice should specify payment method
- Withholding tax: HK has no withholding tax on most payments, but invoices to certain jurisdictions may need tax documentation — flag when relevant
- Invoice requirements: HK does not have GST/VAT, simplifying invoice format, but invoices should include the company's Business Registration number
- Common currency pairs for HK trade: USD/HKD, CNH/HKD, EUR/HKD, GBP/HKD, JPY/HKD — pre-configure these for quick access
- Banking relationships: Many HK traders maintain multi-currency accounts at HSBC, Standard Chartered, Bank of China (HK), or Hang Seng Bank — tool should support multiple bank account configurations

## Data Model

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    default_currency TEXT DEFAULT 'USD',
    payment_terms_days INTEGER DEFAULT 30,
    credit_limit REAL,
    notes TEXT
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    invoice_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    invoice_type TEXT CHECK(invoice_type IN ('sales','purchase','debit_note','credit_note')),
    invoice_date DATE,
    due_date DATE,
    currency TEXT NOT NULL,
    subtotal REAL,
    total REAL,
    hkd_equivalent REAL,
    fx_rate_used REAL,
    fx_rate_date DATE,
    payment_method TEXT,
    status TEXT CHECK(status IN ('draft','sent','partially_paid','paid','overdue','cancelled')) DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id),
    description TEXT,
    quantity REAL,
    unit_price REAL,
    amount REAL,
    hs_code TEXT,
    notes TEXT
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id),
    payment_date DATE,
    amount REAL,
    currency TEXT,
    fx_rate_at_payment REAL,
    hkd_equivalent REAL,
    payment_method TEXT,
    bank_reference TEXT,
    fx_gain_loss REAL,
    notes TEXT
);

CREATE TABLE fx_rates (
    id INTEGER PRIMARY KEY,
    base_currency TEXT DEFAULT 'HKD',
    target_currency TEXT,
    rate REAL,
    source TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bank_accounts (
    id INTEGER PRIMARY KEY,
    bank_name TEXT,
    account_number TEXT,
    currency TEXT,
    account_type TEXT,
    swift_code TEXT,
    active BOOLEAN DEFAULT TRUE
);
```

## Testing Criteria

- [ ] Generates a professional PDF invoice in USD with correct HKD equivalent at current exchange rate
- [ ] FX rate fetcher retrieves live rates and caches them with <1 hour staleness
- [ ] Payment tracker correctly records a partial payment and updates invoice status to "partially_paid"
- [ ] Aging report shows correct 30/60/90+ day buckets with HKD-normalized totals
- [ ] FX gain/loss calculated correctly when payment currency rate differs from invoice rate
- [ ] Monthly statement aggregates all outstanding invoices for a customer with correct balances
- [ ] Hedging advisor suggests rate locking for a large USD invoice with 90-day payment terms

## Implementation Notes

- FX rate caching: fetch rates every hour during HK trading hours (9:00-17:00 HKT), daily snapshot outside hours; store all historical rates for gain/loss calculations
- Invoice numbering: use configurable prefix format (e.g., "INV-2024-0001") with auto-increment; support fiscal year reset
- PDF invoice template: create a professional, clean template with company logo placeholder, bilingual headers, and clear payment instructions including bank SWIFT details
- FX gain/loss calculation: compare the rate at invoice date vs rate at payment date; record as a separate line item for accounting
- Hedging suggestions: simple rule-based — if invoice >USD 50,000 and payment terms >60 days, suggest considering a forward contract; link to historical volatility data
- Memory budget: ~4GB (LLM for bank statement parsing; plotly charts for FX visualization; core invoice generation is lightweight)
- HKD peg awareness: since USD/HKD fluctuates minimally, FX tracking for USD-denominated invoices can be simplified; focus hedging suggestions on CNH and EUR exposure
- Consider adding a daily FX summary email/WhatsApp message showing rate movements for the trader's active currency pairs
