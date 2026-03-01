# Emergency Flight Finder — Build Status

**Status: PROJECT PARKED (Feb 2026)**
All planned phases complete. Deployed and working. Parked for future iteration.

---

## Context

Built during the **Feb 2026 Iran conflict** for an evacuation scenario: Bahrain (airspace closed) → King Fahd Causeway → Saudi Arabia → fly to China. The user holds a Chinese passport, has up to $10,000 budget, and needs the fastest possible route out.

## Live Deployment

| | |
|---|---|
| **URL** | https://emergency-flight-finder.vercel.app |
| **Repo** | https://github.com/xinyige0-ftw/emergency-flight-finder |
| **Platform** | Vercel (serverless Python FastAPI + static HTML) |
| **Auto-deploy** | Yes — pushes to `main` deploy automatically |

---

## User Preferences (baked into defaults)

| Setting | Value |
|---|---|
| Passengers | 1 |
| Passport | Chinese (CN) |
| Budget | $10,000 USD max (business/first OK) |
| Destination | Anywhere in mainland China |
| Risk tolerance | Moderate (OK Saudi, avoid Iran/Iraq/Qatar/UAE) |
| Speed priority | Balanced — penalize wait more than layover |

---

## Project Structure

```
/Users/G/Documents/emergency-flight-finder/
├── pyproject.toml                  # Package config, `evac` CLI entry point
├── requirements.txt                # Python deps
├── Dockerfile                      # Cloud deployment
├── vercel.json                     # Vercel deployment config
├── .env                            # Local secrets (never committed)
├── scenarios/
│   └── bahrain_to_china.yaml       # Scenario: airports, flights, airspaces
├── static/
│   ├── index.html                  # Mobile-first web UI (source of truth)
│   └── sw.js                       # Service worker — PWA/offline
├── public/
│   ├── index.html                  # Vercel static copy (keep in sync)
│   └── sw.js                       # Vercel static copy
├── api/
│   └── index.py                    # Vercel serverless entry point
└── emergency_flights/
    ├── cli.py                      # Click CLI
    ├── config.py                   # YAML scenario loader
    ├── models.py                   # Pydantic models
    ├── searcher.py                 # FR24 flight status
    ├── routes.py                   # Route planner + scoring
    ├── airspace.py                 # Airspace status
    ├── display.py                  # Rich terminal output
    ├── web.py                      # FastAPI + all API endpoints
    ├── pricing.py                  # Phase 2: price/seat scraping
    ├── alerts.py                   # Phase 3: Twilio SMS/WhatsApp
    ├── intel.py                    # Phase 5: news feeds, NOTAMs
    ├── predictions.py              # Phase 6: patterns, visa checker
    ├── community.py                # Phase 7: translations, UI strings
    ├── crowdsource.py              # Phase 7: X/Twitter, embassy RSS
    └── supabase_store.py           # Phase 7: optional DB persistence
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Mobile web UI |
| `/api/routes` | GET | Routes with scores, prices, recommendation |
| `/api/news` | GET | Conflict news + airspace alerts |
| `/api/notams` | GET | Airport NOTAMs (RUH, JED, DMM, IST) |
| `/api/history` | GET | Historical conflict patterns + predictions |
| `/api/scenarios` | GET | List available scenarios |
| `/api/reports` | GET/POST | Crowdsourced flight reports |
| `/api/reports/{id}/upvote` | POST | Upvote a report |
| `/api/rideshares` | GET/POST | Ride-sharing board |
| `/api/translations` | GET | UI strings (en/zh) |
| `/api/crowdsource` | GET | X posts + embassy advisories |
| `/api/alerts/test` | POST | Send test WhatsApp (requires env vars) |
| `/api/alerts/subscribe` | POST | Register a WhatsApp number |

---

## Key Design Decisions

1. **Speed > Price** — ranking prioritises getting out fast
2. **Balanced scoring** — `score = (wait * 1.5) + ground + flight + (layover * 0.8) + conflict_penalty`
3. **Ground transport** — auto-picks fastest: fly DMM→RUH (1.25h) vs drive (4h)
4. **Dual timezone** — departure in AST (UTC+3), arrival in CST (UTC+8)
5. **All criteria are CLI flags** — every preference overridable at runtime
6. **Vercel serverless** — no server to maintain; auto-deploys from GitHub
7. **Offline-first** — service worker caches last API response; HTML always fetched fresh
8. **File-based state** — history/reports stored in `~/.evac_*` files (no DB required)
9. **Optional Supabase** — set `SUPABASE_URL` + `SUPABASE_KEY` for persistent community data

---

## Completed Phases

### Phase 1 — v1.0: Core CLI ✅
Route scoring, live FR24 status checks, watch mode, all criteria as flags, Rich terminal output.

### Phase 2 — v1.1: Price & Seat Availability ✅
Airline-specific scrapers (Turkish, Saudia, Cathay, Air China, China Southern), Google Flights fallback, seat availability detection, multi-pax check, budget filter with OVER BUDGET badge.

### Phase 3 — v1.2: Alerts ✅ (UI parked)
Twilio SMS + WhatsApp alerts on route status changes. Change detection with 5-min cooldown.
- Backend: `/api/alerts/test`, `/api/alerts/subscribe` fully functional
- Frontend: "What you'll receive" + WhatsApp setup instructions visible; interactive Test/Subscribe form hidden (parked for future, blocked by US carrier SMS registration requirements)
- To re-enable: unhide the `testCard` and `smsCard` divs in `index.html`
- Env vars needed: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `EVAC_ALERT_WHATSAPP`

### Phase 4 — v1.3: Web UI ✅
Mobile-first dark theme PWA, auto-refresh, filter controls, one-tap book/call buttons, deployed to Vercel.

### Phase 5 — v1.4: Intelligence ✅
RSS news integration (Al Jazeera, Reuters, BBC, FlightGlobal, UK FCDO), keyword NLP classification, auto-detect airspace changes from headlines, NOTAM parser, airport departure board scraper.

### Phase 6 — v1.5: Smart Predictions ✅
Historical conflict pattern database (7 conflicts), status snapshot recording, trend analysis (trend_up/down/stable), "Wait vs Go Now" recommendation, transit visa checker by passport.

### Phase 7 — v2.0: Community ✅
X/Twitter posts (Nitter RSS fallback; Twitter API v2 if `TWITTER_BEARER_TOKEN` set), UK FCDO embassy advisories (Atom RSS), Supabase persistence option, multi-language EN/ZH, rate limiting, input validation.

### Phase 8 — v2.1: Mobile UI Overhaul ✅
- Base font 15px, 44–48px tap targets throughout
- Collapsible filter bar (⚙ More/Less toggle for Passengers + Budget)
- Tab bar with emoji icons (📋 📰 🏛️ 📡 🔔), sticky positioning, 48px height
- Route cards: 14px rounded corners, deeper shadows, richer badge colours with contrast
- Recommendation bar: emoji icons (✈️ go / ⏳ wait / ⚠️ uncertain) replacing `>>>` / `...`
- Bottom refresh bar: `env(safe-area-inset-bottom)` for iPhone notch
- Alerts tab: larger step text, styled WhatsApp join-code chip
- Service worker v5: HTML never cached (always fresh), aggressive old-cache purge on activate

---

## Environment Variables

| Variable | Used by | Required |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | alerts.py | For SMS/WhatsApp |
| `TWILIO_AUTH_TOKEN` | alerts.py | For SMS/WhatsApp |
| `TWILIO_FROM_NUMBER` | alerts.py | For SMS |
| `EVAC_ALERT_PHONE` | alerts.py | Target SMS number |
| `EVAC_ALERT_WHATSAPP` | alerts.py | Target WhatsApp number |
| `TWITTER_BEARER_TOKEN` | crowdsource.py | For real X/Twitter posts |
| `SUPABASE_URL` | supabase_store.py | For DB persistence |
| `SUPABASE_KEY` | supabase_store.py | For DB persistence |
| `PRICE_API_URL` | pricing.py | Optional external price API |

---

## Known Limitations & Future Work

| Item | Notes |
|---|---|
| SMS alerts blocked | US A2P 10DLC registration required for app-to-person SMS. Use WhatsApp instead. |
| Nitter scraping fragile | Public Nitter instances often 403/bot-challenge. Set `TWITTER_BEARER_TOKEN` for reliable X data. |
| US embassy feeds blocked | State Dept feeds CAPTCHA-protected. UK FCDO feeds work reliably. |
| Price scraping | Best-effort HTML scraping; airlines change their pages. Consider a paid flight data API for production. |
| NOTAM API rate limits | FAA NOTAM API has undocumented rate limits — handle gracefully if 429s appear. |
| Community data local-only | Without Supabase env vars, reports/rides are stored in `~/.evac_*` files — lost on Vercel restarts. Set Supabase vars for persistence. |
| Real-time push | Currently polling only. Could add WebSockets or SSE for instant alerts in a future iteration. |
