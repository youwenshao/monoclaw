# BizOwner OS

## Overview

BizOwner OS is a unified dashboard that integrates WhatsApp Business API, POS (Point of Sale) data, and basic accounting into a single pane of glass for Hong Kong small business owners. It provides a real-time view of daily sales, customer messages, inventory levels, and cash flow — replacing the fragmented spreadsheet-and-WhatsApp workflow that most HK SMEs rely on. Everything runs locally for data privacy and zero subscription costs.

## Target User

Hong Kong small business owners — restaurant operators, retail shop owners, service providers, and micro-businesses with 1-20 employees — who currently manage their business across WhatsApp groups, handwritten receipts, and Excel spreadsheets, and want a centralized view of their operations.

## Core Features

- **WhatsApp Business Dashboard**: Unified inbox for all customer WhatsApp messages with quick-reply templates, auto-responses for common queries (business hours, menu, pricing), and message tagging for follow-up
- **POS Integration**: Connects to common HK POS systems to pull daily sales data, transaction history, and product-level revenue breakdowns
- **Basic Accounting**: Simple income/expense tracking with receipt photo upload; auto-categorizes transactions; generates profit & loss summaries and cash flow reports
- **Daily Digest**: Morning summary via WhatsApp showing yesterday's sales total, today's appointments/orders, pending customer messages, and low-stock alerts
- **Customer CRM**: Lightweight customer database built from WhatsApp contacts and POS transaction history; tracks purchase frequency, total spend, and last interaction
- **Inventory Alerts**: Monitors stock levels from POS data and sends WhatsApp alerts when items fall below configurable thresholds

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Messaging | Twilio WhatsApp Business API for customer communication management |
| POS | HTTP/webhook integrations with common HK POS APIs (Lightspeed, Square, iCHEF) |
| LLM | MLX local inference for auto-categorizing expenses and generating daily digest summaries |
| Database | SQLite for sales data, customer records, expenses, and inventory |
| UI | Streamlit dashboard with sales charts, message inbox, and accounting views |
| Charts | plotly for revenue trends, category breakdowns, and cash flow visualization |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/biz-owner-os/
├── app.py                        # Streamlit unified dashboard
├── whatsapp/
│   ├── inbox_manager.py          # WhatsApp message aggregation and management
│   ├── auto_responder.py         # Template-based and AI auto-responses
│   └── broadcast.py              # Promotional message broadcasting
├── pos/
│   ├── pos_connector.py          # POS system API integration (multi-provider)
│   ├── sales_aggregator.py       # Daily/weekly/monthly sales rollups
│   └── inventory_tracker.py      # Stock level monitoring from POS data
├── accounting/
│   ├── transaction_logger.py     # Income/expense recording with receipt photos
│   ├── categorizer.py            # AI-powered transaction categorization
│   ├── pnl_report.py             # Profit & loss report generation
│   └── cash_flow.py              # Cash flow tracking and forecasting
├── crm/
│   ├── customer_database.py      # Customer profile management
│   └── engagement_tracker.py     # Purchase frequency and recency tracking
├── digest/
│   ├── daily_digest.py           # Morning business summary generation
│   └── alert_engine.py           # Low-stock and follow-up alerts
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Categorization and digest generation prompts
├── data/
│   └── bizowner.db               # SQLite database
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/biz-owner-os/
├── bizowner.db                       # SQLite database (sales, customers, expenses, inventory)
├── receipts/                         # Uploaded receipt photos
└── exports/                          # Generated P&L reports and data exports
```

## Key Integrations

- **Twilio WhatsApp Business API**: Customer message management and business digest delivery
- **POS Systems**: REST API connectors for Lightspeed, Square, iCHEF (popular HK F&B POS)
- **Local LLM (MLX)**: Expense categorization, daily digest narrative generation
- **Receipt OCR** (optional): Tesseract for extracting amounts from photographed receipts
- **Telegram Bot API**: Secondary channel for business alerts, customer communication, and payment reminders.

## GUI Specification

Part of the **Solopreneur Dashboard** (`http://mona.local:8506`) — BizOwner OS tab.

### Views

- **Boss Mode** (default): Three large KPI cards — today's revenue, pending WhatsApp messages, current cash position. Designed for at-a-glance morning check.
- **Revenue Dashboard**: Daily/weekly/monthly revenue trend chart with toggle. Breakdown by payment method (cash, Octopus, FPS, credit card). Top-selling items.
- **WhatsApp Inbox**: Unified customer message feed with auto-response status indicators (handled/pending/needs attention). Quick-reply templates.
- **Quick Actions Bar**: One-click buttons for: record expense, add manual sale, broadcast WhatsApp message, generate daily report.
- **Inventory Alerts**: Low-stock items displayed as warning cards with reorder suggestions and supplier quick-contact buttons.
- **Customer CRM**: Lightweight customer cards built from WhatsApp contacts and POS data. Purchase frequency, total spend, last interaction.

### Mona Integration

- Mona syncs POS data automatically and updates revenue dashboards in real-time.
- Mona handles routine WhatsApp customer inquiries (hours, menu, pricing) and escalates complex ones to the inbox.
- Human reviews daily digest, records manual transactions, and composes promotional messages.

### Manual Mode

- Business owner can manually record sales/expenses, manage the WhatsApp inbox, view reports, and track inventory without Mona.

## HK-Specific Requirements

- Common HK POS systems: iCHEF (popular for restaurants), Lightspeed (retail), Square (multi-purpose), EPOS (local HK system) — prioritize iCHEF and Lightspeed for initial integration
- WhatsApp dominance: WhatsApp is the primary business communication tool in HK — the WhatsApp inbox is the most critical feature for HK SMEs
- HKD-centric: All financial data in HKD; support Octopus and FPS payment method categorization alongside cash and credit card
- Business Registration: HK businesses have a BR (Business Registration) number — include in invoices and reports
- Tax simplicity: HK has no GST/VAT/sales tax, simplifying the accounting module — focus on profits tax (8.25% on first HK$2M, 16.5% thereafter for corporations)
- MPF awareness: Dashboard should remind business owners of monthly MPF contribution deadlines (on or before the contribution day, typically within the first 10 days of the following month)
- Rental costs: Rent is typically the largest expense for HK small businesses — provide special tracking and lease renewal reminders
- Bilingual: Dashboard and WhatsApp auto-responses must support English and Traditional Chinese

## Data Model

```sql
CREATE TABLE sales (
    id INTEGER PRIMARY KEY,
    pos_transaction_id TEXT,
    sale_date TIMESTAMP,
    total_amount REAL,
    payment_method TEXT CHECK(payment_method IN ('cash','credit_card','octopus','fps','alipay','wechat_pay','other')),
    items TEXT,  -- JSON array of items sold
    customer_phone TEXT,
    pos_source TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE expenses (
    id INTEGER PRIMARY KEY,
    expense_date DATE,
    category TEXT CHECK(category IN ('rent','salary','inventory','utilities','marketing','equipment','mpf','insurance','other')),
    description TEXT,
    amount REAL,
    receipt_photo TEXT,
    payment_method TEXT,
    recurring BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    phone TEXT UNIQUE,
    name TEXT,
    name_tc TEXT,
    whatsapp_enabled BOOLEAN DEFAULT TRUE,
    total_spend REAL DEFAULT 0,
    visit_count INTEGER DEFAULT 0,
    last_visit DATE,
    tags TEXT,  -- JSON array
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE inventory (
    id INTEGER PRIMARY KEY,
    item_name TEXT,
    item_name_tc TEXT,
    current_stock INTEGER,
    low_stock_threshold INTEGER DEFAULT 10,
    unit_cost REAL,
    last_updated TIMESTAMP
);

CREATE TABLE whatsapp_messages (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    direction TEXT CHECK(direction IN ('inbound','outbound')),
    message_text TEXT,
    message_type TEXT,
    tags TEXT,
    requires_followup BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Business Profile**: Business name, BR number, business type, operating hours, base currency (HKD)
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
3. **POS Integration**: Connect POS system (iCHEF, Lightspeed, Square) via API or configure CSV import
4. **Payment Methods**: Configure accepted payment methods (cash, Octopus, FPS, credit card, AlipayHK, WeChat Pay)
5. **MPF Trustee**: Select MPF trustee and upload remittance statement template
6. **Social Accounts**: Connect Instagram Business, Facebook Page, and WhatsApp Business accounts
7. **Sample Data**: Option to seed demo sales, expenses, and employees for testing
8. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] WhatsApp auto-responder replies with business hours when customer sends "what time do you open?"
- [ ] POS connector pulls yesterday's sales data and displays correct daily total on dashboard
- [ ] Expense categorizer correctly classifies "rent payment Central office" as category "rent"
- [ ] Daily digest WhatsApp message includes yesterday's revenue, today's pending messages count, and low-stock items
- [ ] Customer CRM shows correct total spend and visit frequency aggregated from POS transactions
- [ ] P&L report generates correct monthly profit figure (revenue minus expenses)
- [ ] Inventory alert fires WhatsApp notification when a product drops below threshold

## Implementation Notes

- POS integration priority: start with iCHEF (most popular HK F&B POS) — they have a REST API; fall back to CSV import for POS systems without APIs
- WhatsApp auto-response: implement keyword-based routing first (fast, no LLM needed); use LLM only for messages that don't match any keyword template
- Accounting simplicity: this is not a full accounting system — it's designed for business owners who currently use spreadsheets; avoid overwhelming with accounting jargon
- Daily digest timing: send at 8:00 AM HKT by default; configurable per user
- Customer deduplication: match POS customers to WhatsApp contacts by phone number (HK 8-digit format)
- Memory budget: ~4GB (LLM for categorization + Streamlit dashboard); POS sync runs as periodic background task
- Receipt OCR: optional feature — many HK small businesses still receive handwritten receipts; Tesseract + LLM extraction provides reasonable accuracy
- Consider implementing a "boss mode" — simplified mobile-friendly view that shows only the 3 most important numbers: today's revenue, pending messages, cash position
- **Logging**: All operations logged to `/var/log/openclaw/biz-owner-os.log` with daily rotation (7-day retention). Financial data and customer details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Business financial data protected under PDPO — zero cloud processing for transaction data.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, POS sync status, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all business data for backup or accountant handoff.
