# Emergency Flight Finder — Requirements Specification

**Status: ALL PHASES COMPLETE — PROJECT PARKED Feb 2026**

---

## 1. Purpose

A CLI + mobile web tool to find the **fastest, most reliable way to evacuate by air** from a conflict zone when normal booking tools are useless — airports closed, airspace shut, airlines cancelling without notice.

Built for a real scenario: evacuating from Bahrain to China during the Feb 2026 Iran conflict.

---

## 2. User Profile

| Field | Value |
|---|---|
| Passengers | 1 (configurable) |
| Passport | Chinese (CN) |
| Origin | Bahrain (airspace CLOSED) |
| Land escape | King Fahd Causeway → Dammam, Saudi Arabia |
| Destination | Anywhere in mainland China (flexible) |
| Budget | Up to $10,000 USD (business/first class acceptable) |
| Booking preference | Both online links AND phone numbers |

---

## 3. Ranking Criteria

### 3.1 Speed — BALANCED mode ✅
- `score = (wait_hours * 1.5) + ground_hours + flight_hours + (layover_hours * 0.8)`
- Dual timezone display: departure in AST (UTC+3), arrival in CST (UTC+8)

### 3.2 Availability ✅
- Live flight status via FR24
- Conflict proximity scoring (LOW / MED / HIGH / BLOCKED)
- Seat availability detection

### 3.2.1 Live Refresh ✅
- `--watch` mode, `--refresh-interval N`
- `[CHANGED]` badge + bell on status change
- `[STALE]` warning for data > 15 min old
- Offline fallback with last-known-data display

### 3.3 Price ✅
- Economy + business class prices scraped from airline sites
- $10,000 budget cap with OVER BUDGET badge
- Google Flights fallback

### 3.4 Accuracy ✅
- FR24 primary status source, cross-referenced with airline sites
- Timestamps on all live data

### 3.5 Booking ✅
- Direct airline booking URLs, pre-filled where possible
- Same-airline multi-leg: single booking button
- Phone numbers for every airline (Saudi office)

---

## 4. Route Planning ✅

### 4.1 Ground segments
| Segment | Mode | Est. time |
|---|---|---|
| Bahrain → Dammam | Drive (causeway) | 1.5h |
| Dammam → Riyadh | Drive / domestic flight | 4.0h / 1.25h |
| Riyadh → Jeddah | Domestic flight | 2.0h |

### 4.2 Key flight routes
**Direct to China:** CZ5008, SV884, CX644, CA790, SV882
**Via Istanbul (lowest risk):** TK145 + TK88/TK26/TK72

### 4.3 Conflict proximity scoring ✅
| Airspace | Risk |
|---|---|
| Saudi → Turkey → China | LOW |
| Saudi → direct eastbound | MEDIUM |
| Over Iran/Iraq | HIGH |
| Via UAE/Qatar | BLOCKED |

---

## 5. Display Requirements ✅

- Route cards with rank, reliability badge, departure/arrival times, total time breakdown
- Badges: risk level, seat availability, OVER BUDGET, CHANGED
- Expandable card body: scoring explanation, flight legs with takeoff/landing times, book/call buttons
- Summary recommendation banner (✈️ Go Now / ⏳ Wait / ⚠️ Uncertain)
- Timestamps on all live data

---

## 6. Data Sources ✅

| Source | Used for |
|---|---|
| FlightRadar24 | Live flight status (primary) |
| Airline websites | Price scraping |
| Google Flights | Price fallback |
| FAA NOTAM API | Aviation notices |
| Al Jazeera / Reuters / BBC / FlightGlobal RSS | Conflict news |
| UK FCDO Atom feeds | Embassy travel advisories |
| Twitter API v2 / Nitter | X/Twitter posts |
| Twilio | SMS/WhatsApp alerts |
| Supabase (optional) | Community data persistence |

---

## 7. CLI Commands ✅

```bash
evac find -s bahrain_to_china
evac find --watch
evac find --watch --refresh-interval 2
evac find --offline
evac status CX644
evac list-scenarios
evac serve                           # web UI
```

---

## 8. Build Phases — All Complete

### Phase 1 — v1.0: Core Evacuation Finder ✅
- [x] Scenario-based YAML config
- [x] Ground escape route planning (fastest-path selection)
- [x] Known flight database with schedule logic
- [x] Live flight status (FR24)
- [x] Route ranking by speed
- [x] Rich terminal display with action steps
- [x] Balanced scoring formula
- [x] Three speed modes: soonest / shortest_total / balanced
- [x] Dual timezone display (AST / CST)
- [x] Booking links + phone numbers
- [x] Price estimates
- [x] `--watch` mode with `[CHANGED]` alerts + bell
- [x] `[STALE]` warnings
- [x] Conflict proximity scoring
- [x] Summary table
- [x] All criteria as CLI flags
- [x] `--sort`, `--max-stops`, `--max-wait`, `--hide-cancelled`
- [x] Offline fallback
- [x] `evac status <flight>`

### Phase 2 — v1.1: Price & Seat Availability ✅
- [x] Price scraping from official airline booking pages
- [x] Google Flights fallback
- [x] Seat availability detection
- [x] Multi-passenger seat check
- [x] Budget filter with OVER BUDGET badge

### Phase 3 — v1.2: Alerts & Notifications ✅ (interactive UI parked)
- [x] SMS alerts via Twilio
- [x] WhatsApp alerts (more reliable than SMS in conflict zones)
- [x] Alert triggers: cancellation, reinstatement, airspace change, new route
- [x] Alert cooldown (5 min per route)
- [x] File-based subscription persistence (`~/.evac_alert_subscriptions.json`)
- [x] WhatsApp setup instructions in UI
- [ ] Interactive test/subscribe UI — parked (US A2P 10DLC registration blocks SMS delivery)

### Phase 4 — v1.3: Web UI (Mobile-First) ✅
- [x] Mobile-first dark theme
- [x] One-tap call / book buttons
- [x] Auto-refresh with countdown timer
- [x] PWA with service worker (offline capable)
- [x] Deployed to Vercel with permanent URL
- [x] Filter controls: speed, sort, max stops
- [x] Language toggle (EN / 中文)

### Phase 5 — v1.4: Intelligence & Data Sources ✅
- [x] RSS news feed integration (Al Jazeera, Reuters, BBC, FlightGlobal)
- [x] Keyword NLP classification (region + airspace + conflict)
- [x] Auto-detect airspace reopenings/closures from headlines
- [x] NOTAM parser (FAA endpoint, shown in Intel tab)
- [x] Airport departure board scraper (FR24)

### Phase 6 — v1.5: Smart Predictions ✅
- [x] Historical conflict pattern database (7 conflicts)
- [x] Status snapshot recording for trend analysis
- [x] Pattern detection: trend_up / trend_down / stable
- [x] "Wait vs Go Now" recommendation engine
- [x] Transit visa checker per passport type

### Phase 7 — v2.0: Community & Crowdsource ✅
- [x] X/Twitter posts (API v2 or Nitter RSS fallback)
- [x] UK FCDO embassy travel advisories (Atom RSS)
- [x] Crowdsourced flight reports with upvoting
- [x] Ride-sharing board for ground segments (backend complete, UI hidden until users active)
- [x] Multi-language: English + Chinese
- [x] Optional Supabase persistence
- [x] Rate limiting + input validation on POST endpoints

### Phase 8 — v2.1: Mobile UI Overhaul ✅
- [x] Base font 15px; all tap targets ≥ 44px
- [x] Collapsible filter bar (main row + expandable More panel)
- [x] Tab bar with emoji icons, 48px height, sticky
- [x] Route cards: larger radius, better badge contrast
- [x] Recommendation banner with ✈️ / ⏳ / ⚠️ emoji icons
- [x] iPhone notch safe-area in bottom bar
- [x] Service worker v5: HTML never cached, aggressive old-cache purge

---

## Deferred / Future

| Item | Reason deferred |
|---|---|
| SMS interactive alerts UI | US A2P 10DLC registration required; WhatsApp is the working alternative |
| Real-time push (WebSockets/SSE) | Polling sufficient for the use case; adds complexity |
| Real-time chat between evacuees | Nice to have; low priority vs core routing |
| Arabic UI translation | Deprioritised; EN + ZH covers the primary user |
| Paid flight data API | Free scraping works for now; revisit if reliability becomes an issue |
| Embassy evacuation flight integration | Hard to automate; recommend checking embassy websites manually |
