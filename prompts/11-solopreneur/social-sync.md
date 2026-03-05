# SocialSync

## Overview

SocialSync is a one-click social media distribution tool that publishes content simultaneously to Instagram, Facebook, and WhatsApp Status from a single interface. It optimizes posts for each platform's format requirements, schedules content for optimal engagement times in the HK market, and provides basic analytics. Designed for Hong Kong solopreneurs and small businesses who manage their own social media without a dedicated marketing team.

## Target User

Hong Kong solopreneurs, small business owners, freelancers, and micro-influencers who post regularly across social platforms to promote their business but lack the time or budget for professional social media management tools.

## Core Features

- **One-Click Multi-Post**: Compose once, publish to Instagram (feed/stories/reels), Facebook (page posts/stories), and WhatsApp Status simultaneously with platform-specific formatting applied automatically
- **Image/Video Optimization**: Auto-resizes and crops images/videos for each platform's optimal dimensions (IG square 1080x1080, IG story 1080x1920, FB 1200x630)
- **Content Calendar**: Visual scheduling calendar with drag-and-drop; queue posts for future publication at optimal times
- **HK-Optimized Scheduling**: Pre-configured optimal posting times for the HK market (lunch 12:00-13:00, evening 19:00-21:00, late night 22:00-23:00)
- **CTA Optimization**: AI-powered suggestions for calls-to-action adapted for HK consumer behavior (WhatsApp click-to-chat, FPS payment links, location-based CTAs)
- **Basic Analytics**: Tracks post reach, engagement, and follower growth across platforms; generates weekly performance summaries

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Social APIs | Instagram Graph API (via Facebook), Facebook Pages API, WhatsApp Business API (via Twilio) |
| Image Processing | Pillow for image resizing, cropping, and optimization; moviepy for basic video processing |
| LLM | MLX local inference for caption optimization, hashtag suggestions, and CTA generation |
| Scheduler | APScheduler for scheduled post publication |
| Database | SQLite for content calendar, post history, and analytics data |
| UI | Streamlit dashboard with content editor, calendar view, and analytics charts |
| Charts | plotly for engagement analytics visualization |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/social-sync/
├── app.py                        # Streamlit social media dashboard
├── publishing/
│   ├── instagram_publisher.py    # Instagram Graph API posting
│   ├── facebook_publisher.py     # Facebook Pages API posting
│   ├── whatsapp_status.py        # WhatsApp Status publishing
│   └── multi_publisher.py        # Orchestrates simultaneous cross-platform posting
├── content/
│   ├── image_optimizer.py        # Platform-specific image resizing and cropping
│   ├── video_optimizer.py        # Video format conversion and optimization
│   ├── caption_optimizer.py      # AI caption enhancement and hashtag suggestions
│   └── cta_generator.py          # HK-optimized CTA generation
├── scheduling/
│   ├── calendar_manager.py       # Content calendar management
│   ├── scheduler.py              # APScheduler-based publication scheduling
│   └── optimal_times.py          # HK market optimal posting time engine
├── analytics/
│   ├── ig_analytics.py           # Instagram insights retrieval
│   ├── fb_analytics.py           # Facebook page insights
│   └── report_generator.py       # Weekly performance summary
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Caption optimization and CTA prompts
├── data/
│   └── socialsync.db             # SQLite database
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/social-sync/
├── socialsync.db                     # SQLite database (posts, analytics, calendar)
├── media/
│   ├── originals/                    # Original uploaded images and videos
│   └── optimized/                    # Platform-specific optimized media
└── exports/                          # Analytics reports and data exports
```

## Key Integrations

- **Instagram Graph API**: Publishing feed posts, stories, and reels; reading insights
- **Facebook Pages API**: Publishing page posts and stories; reading page insights
- **Twilio WhatsApp Business API**: WhatsApp Status updates and click-to-chat link generation
- **Local LLM (MLX)**: Caption optimization, hashtag generation, and CTA suggestions
- **Telegram Bot API**: Secondary channel for business alerts, customer communication, and payment reminders.

## GUI Specification

Part of the **Solopreneur Dashboard** (`http://mona.local:8506`) — SocialSync tab.

### Views

- **Post Composer**: Rich text editor with image/video upload. Multi-platform preview showing how the post will appear on Instagram, Facebook, and WhatsApp simultaneously.
- **Content Calendar**: Monthly calendar with drag-drop post scheduling. Scheduled posts shown as colored cards. Edit or reschedule by dragging.
- **Platform Connections**: Status indicators for connected social accounts (IG Business, FB Page, WhatsApp Business) with reconnect controls.
- **Engagement Analytics**: Per-platform metrics (likes, comments, shares, reach) charted over time. Best posting time recommendations.
- **Template Gallery**: Reusable post templates for common promotions (new product, holiday special, seasonal sale).

### Mona Integration

- Mona suggests optimal posting times based on historical engagement data.
- Mona auto-posts scheduled content at the configured times across all platforms.
- Human creates content, reviews scheduling, and responds to engagement.

### Manual Mode

- Business owner can manually compose posts, schedule content, connect platforms, and view analytics without Mona.

## HK-Specific Requirements

- Platform usage in HK: WhatsApp is #1 messaging app (90%+ penetration), Instagram is the primary social discovery platform for 18-45 demographic, Facebook remains important for 35+ demographic and community groups
- HK posting times: Optimal engagement windows are lunch (12:00-13:00 HKT), evening commute (18:00-19:00), prime time (20:00-22:00), and late night (22:00-00:00) — these differ from US-centric defaults in global tools
- WhatsApp click-to-chat: HK businesses heavily use wa.me links (e.g., `wa.me/852XXXXXXXX`) as CTAs — auto-generate these from the business phone number
- FPS payment links: For product-selling businesses, CTA can include FPS QR code or payment link
- Bilingual content: Many HK businesses post in both English and Traditional Chinese; support dual-language captions with configurable primary/secondary language
- HK hashtag culture: Popular local hashtags (#hkfoodie, #hkig, #852, #hongkong, #hklife) should be suggested alongside niche-specific hashtags
- Seasonal HK events: Calendar should pre-load key HK marketing moments — Chinese New Year, Mid-Autumn Festival, Christmas (massive in HK), 11.11 Singles' Day, Black Friday
- Instagram shopping: Many HK small businesses sell directly via Instagram DMs — integrate with the CRM feature to track DM-sourced leads

## Data Model

```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    content_text TEXT,
    content_text_tc TEXT,
    image_paths TEXT,  -- JSON array of local image paths
    video_path TEXT,
    hashtags TEXT,  -- JSON array
    cta_text TEXT,
    cta_link TEXT,
    scheduled_time TIMESTAMP,
    status TEXT CHECK(status IN ('draft','scheduled','publishing','published','failed')) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE platform_posts (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    platform TEXT CHECK(platform IN ('instagram_feed','instagram_story','instagram_reel','facebook_page','facebook_story','whatsapp_status')),
    platform_post_id TEXT,
    publish_status TEXT CHECK(publish_status IN ('pending','published','failed')),
    published_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE analytics (
    id INTEGER PRIMARY KEY,
    platform_post_id INTEGER REFERENCES platform_posts(id),
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_calendar (
    id INTEGER PRIMARY KEY,
    date DATE,
    theme TEXT,
    notes TEXT,
    post_ids TEXT,  -- JSON array of post IDs
    is_hk_event BOOLEAN DEFAULT FALSE,
    event_name TEXT
);

CREATE TABLE hashtag_library (
    id INTEGER PRIMARY KEY,
    hashtag TEXT UNIQUE,
    category TEXT,
    avg_engagement REAL,
    usage_count INTEGER DEFAULT 0,
    language TEXT DEFAULT 'en'
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Business Profile**: Business name, BR number, business type, operating hours, base currency (HKD)
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
3. **Social Accounts**: Connect Instagram Business account, Facebook Page, and WhatsApp Business account; verify API permissions
4. **Content Preferences**: Default posting language (English/Traditional Chinese/bilingual), preferred hashtag categories, brand tone
5. **Scheduling Preferences**: Configure optimal posting times or use HK market defaults (lunch, evening, late night)
6. **Sample Data**: Option to seed demo posts, calendar events, and analytics for testing
7. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] One-click publish sends the same content to Instagram feed, Facebook page, and WhatsApp Status successfully
- [ ] Image optimizer produces correctly sized images for each platform from a single source image
- [ ] Scheduled post publishes at the configured time (within 1-minute accuracy)
- [ ] Caption optimizer suggests relevant HK-specific hashtags (#hkfoodie, #hkig) for a food post
- [ ] CTA generator produces a valid wa.me click-to-chat link with the correct HK phone number
- [ ] Analytics retrieval pulls correct engagement metrics from Instagram for a published post
- [ ] Content calendar shows pre-loaded HK seasonal events (CNY, Mid-Autumn) for the current year

## Implementation Notes

- Instagram Graph API requires a Facebook Business Page linked to the Instagram Professional Account — document this setup clearly in the README
- WhatsApp Status publishing via Twilio may have limitations — verify capability; fall back to generating shareable content that the user manually posts to Status
- Image processing: use Pillow's `ImageOps.fit()` for center-crop to target dimensions; maintain a separate optimized copy per platform rather than modifying originals
- Scheduling: APScheduler's `date` trigger for one-time scheduled posts; store the job ID in the database for cancellation support
- HK optimal times: default schedule based on general HK social media research; allow the business owner to override based on their specific audience analytics
- Analytics API rate limits: Instagram Graph API has strict rate limits — fetch analytics for each post once daily rather than in real-time
- Memory budget: ~4GB (LLM for caption optimization; image processing is done on-demand and released; video processing may spike memory temporarily)
- Consider a "content inspiration" feature that generates post ideas based on upcoming HK events, trending topics, and the business's past top-performing content
- **Logging**: All operations logged to `/var/log/openclaw/social-sync.log` with daily rotation (7-day retention). Financial data and customer details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Business financial data protected under PDPO — zero cloud processing for transaction data.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, POS sync status, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all business data for backup or accountant handoff.
