# Emergency Flight Finder — Build Status

## Context
User is evacuating from **Bahrain to China** during the Feb 2026 Iran conflict.
Bahrain airspace is closed. Plan: cross King Fahd Causeway to Saudi Arabia,
fly from Saudi airports (Dammam/Riyadh/Jeddah) to China.

## User Preferences (defaults for CLI flags)
- **Passengers:** 1
- **Passport:** Chinese (CN) — no visa needed for China, simplifies transit
- **Budget:** $10,000 USD max (business/first OK)
- **Destination:** Anywhere in mainland China
- **Risk tolerance:** Moderate (OK with Saudi airspace, avoid Iran/Iraq/Qatar/UAE)
- **Speed priority:** Balanced (penalize long waits > long layovers)
- **Booking:** Both direct airline URLs + phone numbers

## Project Structure
```
/Users/G/Documents/emergency-flight-finder/
├── pyproject.toml                  # Package config, `evac` CLI entry point
├── requirements.txt                # Python deps
├── Dockerfile                      # Cloud deployment
├── render.yaml                     # Render.com deployment config
├── vercel.json                     # Vercel deployment config
├── scenarios/
│   └── bahrain_to_china.yaml       # Current scenario with all flight data
├── static/
│   ├── index.html                  # Mobile-first web UI
│   └── sw.js                       # Service worker for offline PWA
├── public/
│   ├── index.html                  # Vercel static copy
│   └── sw.js                       # Vercel static copy
├── api/
│   └── index.py                    # Vercel serverless entry point
└── emergency_flights/
    ├── __init__.py
    ├── cli.py                      # Click CLI with all flag options
    ├── config.py                   # YAML scenario loader
    ├── models.py                   # Pydantic models
    ├── searcher.py                 # FR24 flight status checking
    ├── routes.py                   # Route planner + scoring engine
    ├── airspace.py                 # Airspace status module
    ├── display.py                  # Rich terminal output
    ├── web.py                      # FastAPI web server + all API endpoints
    ├── pricing.py                  # Phase 2: Price & seat scraping
    ├── alerts.py                   # Phase 3: Twilio SMS/WhatsApp alerts
    ├── intel.py                    # Phase 5: News feeds, NOTAM parser
    ├── predictions.py              # Phase 6: Historical patterns, visa checker
    └── community.py                # Phase 7: Crowdsourced reports, ride-sharing
```

## Deployment
- **Live URL:** https://emergency-flight-finder.vercel.app
- **GitHub:** https://github.com/xinyige0-ftw/emergency-flight-finder
- Auto-deploys on push to main

## Phase 1 — v1.0: Core Evacuation Finder — COMPLETE
CLI tool with route scoring, live status checks, watch mode, all criteria as flags.

## Phase 2 — v1.1: Price & Seat Availability — COMPLETE
- Airline-specific scrapers (Turkish, Saudia, Cathay, Air China, China Southern)
- Google Flights fallback
- Seat availability detection
- Multi-passenger seat check
- Budget filter (tags over-budget flights)

## Phase 3 — v1.2: Alerts & Notifications — COMPLETE
- Twilio SMS alerts on route status changes
- WhatsApp as alternative channel
- Change detection: status flips, price changes, new/removed routes
- Cooldown to prevent spam (5 min per route)
- Set env vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, EVAC_ALERT_PHONE, EVAC_ALERT_WHATSAPP

## Phase 4 — v1.3: Web UI (Mobile-First) — COMPLETE
- Mobile-first dark theme with large tap targets
- One-tap call/book buttons
- Auto-refresh with countdown timer
- PWA with service worker (offline capable)
- Deployed to Vercel with permanent URL
- Filter controls: speed priority, sort, max stops

## Phase 5 — v1.4: Intelligence & Data Sources — COMPLETE
- RSS news feed integration (Al Jazeera, Reuters, BBC, FlightGlobal)
- Keyword NLP classification (region + airspace + conflict)
- Auto-detect potential airspace reopenings/closures from headlines
- NOTAM parser (FAA endpoint)
- Airport departure board scraper (FR24)
- API endpoints: /api/news, /api/notams

## Phase 6 — v1.5: Smart Predictions — COMPLETE
- Historical conflict pattern database (Gulf War, Iraq 2003, Yemen, Qatar blockade, Ukraine, Iran-Israel 2024)
- Status snapshot recording for trend analysis
- Pattern detection: trend_up, trend_down, stable
- "Wait vs Go Now" recommendation engine
- Transit visa checker per passport type (CN passport: Turkey, UK, Ethiopia, Qatar, UAE, etc.)
- API endpoints: /api/history

## Phase 7 — v2.0: Multi-Scenario & Community — COMPLETE
- Multiple scenario support (/api/scenarios)
- Crowdsourced flight/airport status reports (/api/reports)
- Report upvoting for community validation
- Ride-sharing board for ground segments (/api/rideshares)
- Multi-language support: English, Chinese (中文), Arabic (العربية)
- Translation API: /api/translations?lang=zh

## Key Design Decisions
1. **Speed > Price**: Ranking prioritizes getting out fast
2. **Balanced scoring**: `score = (wait * 1.5) + ground + flight + (layover * 0.8) + conflict_penalty`
3. **Ground transport**: Auto-picks fastest (fly DMM→RUH 1.25h vs drive 4h)
4. **Dual timezone**: Departure in AST (UTC+3), arrival in CST (UTC+8)
5. **All criteria are CLI flags**: Every preference can be overridden at runtime
6. **Vercel deployment**: Serverless Python + static HTML, auto-deploys from GitHub
7. **Offline-first**: Service worker caches pages + last API response
8. **File-based state**: History, reports, rides stored in ~/.evac_* files (no DB needed)

## API Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Mobile web UI |
| `/api/routes` | GET | Route data with scores, prices, recommendations |
| `/api/news` | GET | Conflict news feed with airspace alerts |
| `/api/notams` | GET | Airport NOTAMs |
| `/api/history` | GET | Historical conflict patterns |
| `/api/scenarios` | GET | List available scenarios |
| `/api/reports` | GET/POST | Crowdsourced flight reports |
| `/api/reports/{id}/upvote` | POST | Upvote a report |
| `/api/rideshares` | GET/POST | Ride-sharing board |
| `/api/translations` | GET | UI translations (en/zh/ar) |

---

## Remaining Tasks (not P0)

| Priority | Task | Notes |
|----------|------|-------|
| **P1** | External crowdsource data | Integrate X/Twitter search, Telegram evacuation groups, FR24 community, embassy feeds. Not P0. |
| **P1** | Persist community data | Replace file-based storage with DB (Supabase/Firebase) so reports & rides persist on Vercel. |
| **P2** | Real price scraping | Airlines block scrapers; need headless browser or booking API partners for live prices. |
| **P2** | Service worker | Cache new API endpoints (news, reports, rides) for offline. |
| **P2** | Hardening | Rate limits, input validation on POST /api/reports and /api/rideshares. |
