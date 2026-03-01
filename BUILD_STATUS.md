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
├── REQUIREMENTS.md                 # Full requirements spec + build phases
├── BUILD_STATUS.md                 # This file
├── README.md                       # User-facing docs
├── scenarios/
│   └── bahrain_to_china.yaml       # Current scenario with all flight data
└── emergency_flights/
    ├── __init__.py
    ├── cli.py                      # Click CLI with all flag options
    ├── config.py                   # YAML scenario loader
    ├── models.py                   # Pydantic models (Flight, Route, Scenario, etc.)
    ├── searcher.py                 # FR24 flight status checking
    ├── routes.py                   # Route planner + scoring engine
    ├── airspace.py                 # Airspace status module
    └── display.py                  # Rich terminal output
```

## Phase 1 — v1.0: COMPLETE
Everything works. Run: `evac find --offline` or `evac find` (live) or `evac find -w` (watch).
All user criteria exposed as CLI flags (--speed, --budget, --risk, --sort, etc.).

## Phase 2 — v1.1: Price & Seat Availability — NOT STARTED
- Scrape real prices from airline booking pages (Turkish, Saudia, Cathay, etc.)
- Scrape Google Flights / Skyscanner as fallback
- Detect seat availability (sold out / cabin class)
- Multi-passenger seat check
- Budget filter (hide routes above cap)

## Phase 3 — v1.2: Alerts & Notifications — NOT STARTED
- SMS alerts via Twilio when route status changes
- WhatsApp as alternative channel
- Alert triggers: cancelled→reinstated, airspace reopened, new flight added
- Configurable preferences + cooldown to prevent spam

## Phase 4 — v1.3: Web UI (Mobile-First) — NOT STARTED
- Mobile-first web interface (critical for on-the-move use)
- Same data as CLI, accessible from phone browser
- One-tap call buttons + booking links
- Auto-refresh with push notifications
- Offline-capable PWA
- Shareable URL for family/friends

## Phase 5 — v1.4: Intelligence & Data Sources — NOT STARTED
- Conflict news feed integration (Al Jazeera, Reuters, BBC RSS)
- Auto-detect airspace closures from headlines (keyword NLP)
- Embassy evacuation flight integration
- NOTAM feed parser
- Airport departure board scraper

## Phase 6 — v1.5: Smart Predictions — NOT STARTED
- Historical pattern detection from past conflicts
- Predict flight resumption timing
- Predict airspace reopening
- "Wait vs go now" recommendation
- Transit visa checker per passport type

## Phase 7 — v2.0: Multi-Scenario & Community — NOT STARTED
- Multiple concurrent scenarios
- Crowdsourced flight status reports
- Real-time evacuee chat
- Ride-sharing integration for ground segments
- Multi-language (Chinese, Arabic, English)

## Key Design Decisions Made
1. **Speed > Price**: Ranking prioritizes getting out fast, not saving money
2. **Balanced scoring**: `score = (wait * 1.5) + ground + flight + (layover * 0.8) + conflict_penalty`
3. **Three speed modes**: soonest (wait*3), balanced (wait*1.5), shortest_total (wait*1)
4. **Ground transport**: Auto-picks fastest (fly DMM→RUH 1.25h vs drive 4h)
5. **Conflict proximity**: Routes scored LOW/MED/HIGH risk based on airspace they traverse
6. **Dual timezone**: Departure in AST (UTC+3), arrival in CST (UTC+8)
7. **Watch mode**: Auto-refresh with [CHANGED] badges + terminal bell on status flips
8. **All criteria are CLI flags**: Every preference can be overridden at runtime
9. **Web UI later**: CLI is functional, web UI is Phase 4 (mobile-first PWA)

## Known Flights in Scenario
Direct from Saudi to China:
- CZ5008 China Southern RUH→SZX Tue/Thu/Sat
- SV884 Saudia RUH→CAN Tue/Thu/Sat
- CX644 Cathay Pacific RUH→HKG daily
- CA790 Air China RUH→PEK Mon/Wed/Fri/Sun
- SV882 Saudia JED→CAN Mon/Wed/Fri

Via Istanbul (safest):
- TK145 Turkish Airlines RUH→IST daily
- TK88 Turkish Airlines IST→PEK daily
- TK26 Turkish Airlines IST→PVG daily
- TK72 Turkish Airlines IST→CAN daily

## Live Status (from FlightRadar24, checked Feb 28 2026)
- CX644 Feb 28: CANCELLED (was operating fine through Feb 27)
- CZ5008 Feb 28: UNKNOWN (coin flip — call China Southern)
- SV884: Likely operating but next departure is Tue Mar 3
- TK145: Most likely operating (Turkish airspace unaffected)
