# ListingSync Agent — Multi-Platform Property Listing Distribution

## Overview

ListingSync Agent automates the distribution of property listings across Hong Kong's major real estate platforms. It rewrites listing descriptions for each platform's SEO requirements, formats and resizes images to platform specifications, auto-posts to 28Hse, Squarefoot, and WhatsApp groups, and tracks listing performance across channels.

## Target User

Hong Kong estate agents managing 10-30 active listings who currently spend 2-3 hours daily manually uploading the same listing to multiple portals with slightly different formats, image sizes, and field requirements.

## Core Features

- **Platform-Adaptive Description Rewriting**: Take a single master listing and rewrite for each platform's style — 28Hse (concise Chinese-first), Squarefoot (detailed English-first), agent website (SEO-optimized), WhatsApp groups (punchy one-liner with emoji). Uses local LLM for tone adaptation.
- **Image Processing Pipeline**: Resize photos to each platform's required dimensions, apply agent watermark with EAA license number, auto-enhance (brightness/contrast normalization), and generate platform-specific image sets (e.g., 28Hse max 20 photos, Squarefoot max 30).
- **Automated Multi-Post**: Browser automation to post listings on 28Hse and Squarefoot. Fill form fields from structured listing data, upload processed images, and confirm successful submission. Support for scheduling posts at optimal times.
- **Listing Performance Dashboard**: Track views, inquiries, and days-on-market per platform. Generate weekly reports comparing platform effectiveness. Flag stale listings (>30 days) for price adjustment consideration.
- **WhatsApp Group Broadcast**: Format listing as WhatsApp message (text + images) and distribute to configured agent group chats. Include property highlights, price, and contact info.
- **Listing Lifecycle Management**: Track listing status (active/under-offer/sold/withdrawn) across all platforms. When status changes, update or remove from all platforms in one action.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) |
| Browser automation | `playwright` (Chromium) |
| Image processing | `Pillow`, `pillow-heif` |
| HTTP client | `httpx` |
| Scheduling | `APScheduler` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| WhatsApp | Twilio WhatsApp Business API |
| File watching | `watchdog` |

## File Structure

```
/opt/openclaw/skills/local/listing-sync/
├── main.py                  # FastAPI app + scheduler entry
├── config.yaml              # Platform credentials, watermark settings
├── platforms/
│   ├── base.py              # Abstract platform interface
│   ├── twentyeight_hse.py   # 28Hse automation
│   ├── squarefoot.py        # Squarefoot automation
│   └── whatsapp.py          # WhatsApp group poster
├── processing/
│   ├── description.py       # LLM description rewriter
│   ├── images.py            # Resize, watermark, enhance
│   └── seo.py               # Keyword extraction and injection
├── tracking/
│   ├── performance.py       # Listing analytics
│   └── lifecycle.py         # Status management
├── browser/
│   └── session.py           # Playwright session manager
└── tests/
    ├── test_platforms.py
    ├── test_images.py
    └── test_descriptions.py

~/OpenClawWorkspace/listing-sync/
├── listings/                # Master listing JSON files
├── images/
│   ├── originals/           # Source photos
│   └── processed/           # Platform-ready images
├── watermarks/              # Agent watermark templates
├── exports/                 # Performance reports
└── browser_data/            # Playwright persistent context
```

## Key Integrations

- **28Hse (28hse.com)**: Browser automation for listing creation/update. Parse listing ID after submission for tracking.
- **Squarefoot (squarefoot.com.hk)**: Browser automation with different form structure. Support featured listing placement.
- **Twilio WhatsApp Business API**: Send formatted listing messages to group chats.
- **Agent Website CMS**: Optional REST API integration for agent's own website if available.
- **Google Drive / iCloud**: Watch folder for new listing photos, auto-trigger processing pipeline.

## HK-Specific Requirements

- **EAA License Compliance**: Every listing image must include a visible watermark with the agent's EAA license number (format: E-XXXXXX or S-XXXXXX). Text must be legible at thumbnail size.
- **Saleable Area Mandate**: All descriptions must quote saleable area (實用面積) as the primary measurement. Gross area may be mentioned secondarily. Non-compliant descriptions must be flagged and corrected.
- **28Hse vs Squarefoot Format**: 28Hse uses Traditional Chinese as primary language with specific district/estate dropdown values. Squarefoot uses English-first with different categorization. Map internal estate names to each platform's taxonomy.
- **Price Display**: Show price in HKD with standard formatting (e.g., $1,280萬 for Chinese, HK$12.8M for English). Include price per square foot (saleable).
- **Platform Terms of Service**: Respect rate limits on automated posting. Maximum 5 new listings per hour per account. Implement exponential backoff on failures.
- **Watermark Positioning**: Bottom-right corner, semi-transparent white text on dark overlay strip, minimum 12px font at 1080p resolution.

## Data Model

```sql
CREATE TABLE listings (
    id INTEGER PRIMARY KEY,
    reference_code TEXT UNIQUE NOT NULL,
    title_en TEXT,
    title_zh TEXT,
    description_master TEXT,
    district TEXT,
    estate TEXT,
    address TEXT,
    saleable_area_sqft REAL,
    gross_area_sqft REAL,
    price_hkd INTEGER,
    bedrooms INTEGER,
    bathrooms INTEGER,
    floor TEXT,
    facing TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE platform_posts (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    platform TEXT NOT NULL,
    platform_listing_id TEXT,
    description_adapted TEXT,
    posted_at TIMESTAMP,
    status TEXT DEFAULT 'pending',
    last_checked TIMESTAMP,
    views INTEGER DEFAULT 0,
    inquiries INTEGER DEFAULT 0
);

CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    original_path TEXT,
    processed_paths TEXT,
    watermarked BOOLEAN DEFAULT FALSE,
    sort_order INTEGER
);
```

## Testing Criteria

- [ ] Description rewriting produces distinct, platform-appropriate text for 28Hse (Chinese-first) and Squarefoot (English-first)
- [ ] Images resize correctly to 28Hse specs (1024x768) and Squarefoot specs (1200x900) without distortion
- [ ] Watermark is visible and legible on both light and dark images at thumbnail size
- [ ] Browser automation successfully creates a test listing on 28Hse staging/test account
- [ ] WhatsApp message formatting renders correctly (no broken characters) in both English and Chinese
- [ ] Listing status change propagates to all platforms within 5 minutes
- [ ] Performance tracking correctly counts views from scraping platform listing pages
- [ ] All saleable area values pass EAA compliance check (present and primary)

## Implementation Notes

- **Playwright sessions**: Use persistent browser contexts to maintain login sessions across restarts. Store session data in `~/OpenClawWorkspace/listing-sync/browser_data/`.
- **Image memory**: Process images one at a time to avoid memory spikes. A batch of 20 high-res photos can consume 2GB+ if loaded simultaneously.
- **LLM usage**: Description rewriting is a light task — batch multiple rewrites in a single LLM session to amortize model load time. Each rewrite should take <3 seconds.
- **Failure recovery**: If a platform post fails mid-upload, mark as `failed` with error details. Retry up to 3 times with exponential backoff. Alert agent via WhatsApp after 3 failures.
- **Privacy**: Listing photos may contain tenant belongings. Never send images to external AI services. All image processing happens locally via Pillow.
- **Scheduling**: Optimal posting times for HK property portals are 8-9am and 6-7pm HKT. Default scheduler targets these windows.
