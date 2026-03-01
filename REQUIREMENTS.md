# Emergency Flight Finder — Requirements Specification

## 1. Purpose

A CLI tool to find the **fastest, most reliable way to evacuate by air** from a conflict zone when normal booking tools are useless — airports closed, airspace shut, airlines cancelling without notice.

Built for a real scenario: evacuating from Bahrain to China during the Feb 2026 Iran conflict.

---

## 2. User Profile

| Field              | Value                                                    |
|--------------------|----------------------------------------------------------|
| Passengers         | 1                                                        |
| Passport           | Chinese passport (no visa needed for China entry)        |
| Origin             | Bahrain (airspace CLOSED)                                |
| Land escape        | King Fahd Causeway → Dammam, Saudi Arabia                |
| Destination        | Anywhere in mainland China (flexible)                    |
| Budget             | Up to $10,000 USD (business/first class acceptable)      |
| Booking preference | Both online links AND phone numbers                      |

---

## 3. Ranking Criteria (in priority order)

### 3.1 Speed — BALANCED mode
- Weigh **both** soonest departure AND shortest total door-to-door time
- Penalize **long waits before departure** more heavily than long layovers
- Formula: `score = (wait_hours * 1.5) + ground_hours + flight_hours + (layover_hours * 0.8)`
- Display **next available departure** and **estimated arrival** clearly
- All times shown in **dual timezone**:
  - Departure times in **AST (UTC+3)** — Saudi Arabia local
  - Arrival times in **CST (UTC+8)** — China local

### 3.2 Availability — must be actually bookable
- **Flight status**: Check live status (operating / scheduled / cancelled / unknown)
- **Conflict proximity**: Prefer routes that avoid closed/dangerous airspace
  - OK with Saudi airspace
  - AVOID routing near Iran, Iraq, Qatar, UAE
  - Prefer: Turkey, India, Africa, or direct eastbound over open ocean
- **Seat availability**: Flag if seats are likely available (1 pax easier)
- **Reliability score**: Based on
  - Is the airline still operating from that airport today?
  - Has this specific flight been cancelled recently?
  - How far is the departure airport from the conflict zone?

### 3.2.1 Live Refresh — situation changes fast
During a conflict, everything can change in minutes. The tool **MUST** continuously refresh:

- **Airspace status**: Re-check which countries have opened/closed/restricted airspace
  - A closed airspace can reopen (e.g., UAE may partially reopen within hours)
  - An open airspace can close (e.g., Saudi could restrict if conflict escalates)
  - New NOTAMs (Notices to Air Missions) may alter routing
- **Flight statuses**: Re-poll every cycle for each known flight
  - A "cancelled" flight can be reinstated as the situation stabilizes
  - A "scheduled" flight can be cancelled minutes before departure
  - New flights may be added (relief/repatriation flights, charter flights)
- **Airport operational status**: Airports can close/open at any time
  - Bahrain airport could reopen → changes the entire plan
  - A Saudi airport near the border could be restricted
- **Escape route status**: Border crossings can close
  - King Fahd Causeway could be shut for security
  - Highway conditions can change (military convoys, checkpoints)

**Refresh behavior:**
- **`--watch` mode**: Auto-refresh every N minutes (default: 5 min), highlighting what changed since last check
- **`--refresh-interval N`**: Set custom refresh interval in minutes (min: 1, max: 60)
- **Change alerts**: When a route's status changes (e.g., cancelled → scheduled, or airspace reopens), highlight it prominently with a `[CHANGED]` badge and a sound/bell alert
- **Stale data warning**: If any data is older than 15 minutes, show a `[STALE]` warning next to it
- **Offline fallback**: If network goes down during refresh, keep showing the last known data with a `[OFFLINE — last updated HH:MM]` banner

**What gets refreshed each cycle:**
1. Airspace closure map (scrape aviation NOTAMs / news sources)
2. All known flight statuses (via FR24 / FlightAware)
3. Airport departure boards (are flights actually leaving?)
4. Price/seat availability (if airline sites are reachable)
5. News headlines for new developments (ceasefire, escalation, new closures)

### 3.3 Price
- Show estimated price per person (economy + business if available)
- Budget cap: **$10,000 USD** — filter out anything above
- Cheaper is better as a tiebreaker, but never at the cost of speed/reliability
- Source prices from official airline websites where possible

### 3.4 Accuracy — verify from reliable sources
- **Primary sources** (in order of trust):
  1. Official airline websites (saudia.com, turkishairlines.com, cathaypacific.com, etc.)
  2. FlightRadar24 live tracking (actual aircraft positions)
  3. FlightAware / FlightStats (schedule + status data)
  4. Aggregators (Google Flights, Skyscanner) — for price cross-reference only
- **Cross-reference**: If FR24 says "cancelled" but airline site says "scheduled", flag the conflict
- **Timestamp**: Show when each status was last checked

### 3.5 Booking — direct actionable links
- For each route, provide:
  - **Direct booking URL** to the airline's own website (pre-filled with route/date if possible)
  - **Phone number** for the airline's local (Saudi) office
  - **Alternative booking**: link to Google Flights or similar as fallback
- Phone numbers are critical — internet may be unreliable during conflict

---

## 4. Route Planning Logic

### 4.1 Ground segments
| Segment                | Mode            | Est. time | Notes                                     |
|------------------------|-----------------|-----------|-------------------------------------------|
| Bahrain → Dammam       | Drive (causeway)| 1.5h      | King Fahd Causeway, SAR 35 toll           |
| Dammam → Riyadh        | Drive / flight  | 4.0h / 1.25h | Highway 40 or domestic SV/XY flight   |
| Riyadh → Jeddah        | Domestic flight | 2.0h      | Frequent Saudia/Flynas/Flyadeal flights   |

### 4.2 Flight categories

**Direct to China (fastest if operating):**
| Flight  | Airline          | Route       | Days          | Depart (AST) | Arrive (CST) | Duration |
|---------|------------------|-------------|---------------|--------------|--------------|----------|
| CZ5008  | China Southern   | RUH → SZX   | Tue/Thu/Sat   | 00:30+1      | 13:40        | ~8h10m   |
| SV884   | Saudia           | RUH → CAN   | Tue/Thu/Sat   | 00:40+1      | 18:30        | ~7h50m   |
| CX644   | Cathay Pacific   | RUH → HKG   | Daily*        | 23:50        | 12:55+1      | ~8h05m   |
| CA790   | Air China        | RUH → PEK   | Mon/Wed/Fri/Sun| 00:05+1     | 18:45        | ~8h30m   |
| SV882   | Saudia           | JED → CAN   | Mon/Wed/Fri   | 04:50+1      | 23:25        | ~8h35m   |

**Via Istanbul (most reliable — Turkish airspace unaffected):**
| Flight  | Airline          | Route       | Days   | Depart (AST) | Arrive      | Duration |
|---------|------------------|-------------|--------|--------------|-------------|----------|
| TK145   | Turkish Airlines | RUH → IST   | Daily  | 06:30        | 13:40 (TRT) | ~4h10m   |
| TK88    | Turkish Airlines | IST → PEK   | Daily  | 23:05 (TRT)  | 16:15 (CST) | ~9h10m   |
| TK26    | Turkish Airlines | IST → PVG   | Daily  | 20:25 (TRT)  | 13:35 (CST) | ~10h10m  |
| TK72    | Turkish Airlines | IST → CAN   | Daily  | 20:50 (TRT)  | 14:00 (CST) | ~10h10m  |

### 4.3 Conflict proximity scoring
| Route airspace                | Proximity score | Notes                              |
|-------------------------------|----------------|------------------------------------|
| Saudi → Turkey → China        | LOW risk       | Avoids all conflict zones          |
| Saudi → direct eastbound      | MEDIUM risk    | Passes near Gulf but at altitude   |
| Any route over Iran/Iraq      | HIGH risk      | Airspace closed, not viable        |
| Any route via UAE/Qatar hub   | BLOCKED        | Airports closed                    |

---

## 5. Display Requirements

### 5.1 For each ranked route, show:
```
#1  [RELIABILITY BADGE]  Route Name
    Status: OPERATING / SCHEDULED / CANCELLED / UNKNOWN (with source + timestamp)
    Departs: Sat Mar 01, 06:30 AST  →  Arrives: Sun Mar 02, 16:15 CST
    Total time: ~24.9h (wait: 4.0h + ground: 5.5h + flight: 13.4h + layover: 2.0h)
    Price: ~$850 economy / ~$3,200 business
    Seats: Available / Limited / Unknown
    Risk: LOW — avoids Iran/Iraq/UAE airspace
    
    GROUND: Bahrain → Dammam (causeway, 1.5h) → Riyadh (drive, 4h)
    FLIGHT 1: TK145 RUH→IST  06:30 AST → 13:40 TRT  (4.2h)
    FLIGHT 2: TK88  IST→PEK  23:05 TRT → 16:15 CST  (9.2h)
    
    BOOK: https://www.turkishairlines.com/...
    CALL: +966 11 477 3300
```

### 5.2 Summary table at the top
Quick-glance table showing all routes ranked, before the detailed cards.

### 5.3 Timestamps
Every piece of live data must show when it was last checked.

---

## 6. Data Sources & Booking Links

| Airline          | Official booking URL                              | Phone (Saudi)       |
|------------------|---------------------------------------------------|---------------------|
| Turkish Airlines | https://www.turkishairlines.com/en-sa/            | +966 11 477 3300    |
| Saudia           | https://www.saudia.com/                           | +966 9200 22222     |
| China Southern   | https://www.csair.com/en/                         | +966 11 454 3388    |
| Cathay Pacific   | https://www.cathaypacific.com/                    | +966 11 463 2211    |
| Air China        | https://www.airchina.com/                         | +966 11 211 1333    |
| Google Flights   | https://www.google.com/travel/flights             | —                   |
| Skyscanner       | https://www.skyscanner.com/                       | —                   |

| Status source    | URL                                               | Trust level         |
|------------------|---------------------------------------------------|---------------------|
| FlightRadar24    | https://www.flightradar24.com/data/flights/{code} | HIGH (live tracking)|
| FlightAware      | https://www.flightaware.com/live/flight/{code}    | HIGH (live tracking)|
| FlightStats      | https://www.flightstats.com/                      | MEDIUM (schedule)   |

**Live refresh data sources:**

| Data type             | Source                                                   | Refresh method       |
|-----------------------|----------------------------------------------------------|----------------------|
| Airspace closures     | FAA NOTAM system, ICAO, Eurocontrol                      | Scrape / API poll    |
| Airspace closures     | News feeds (Al Jazeera, Reuters, BBC)                    | Headline keyword scan|
| Airport status        | Official airport sites + FlightStats departure boards    | Scrape               |
| Flight status         | FlightRadar24 flight history pages                       | Scrape per flight    |
| Flight status         | FlightRadar24 Python API (live aircraft positions)       | API call             |
| Border crossing status| News feeds + official causeway/border authority sites     | Scrape               |
| Prices & seats        | Official airline booking pages                           | Scrape (best-effort) |

---

## 7. CLI Commands

```bash
# Full evacuation plan with live checks (single run)
evac find -s bahrain_to_china

# Watch mode — auto-refresh every 5 minutes, alerts on changes
evac find -s bahrain_to_china --watch

# Custom refresh interval (every 2 minutes)
evac find -s bahrain_to_china --watch --refresh-interval 2

# Offline mode (use cached/config data only)
evac find -s bahrain_to_china --offline

# Check single flight status
evac status CX644

# Check single flight status in watch mode
evac status CX644 --watch

# List available scenarios
evac list-scenarios
```

---

## 8. Build Phases

All features below are in scope. Build v1 first, then add each feature incrementally.

### Phase 1 — v1.0: Core Evacuation Finder — COMPLETE
- [x] Scenario-based config (YAML)
- [x] Ground escape route planning (with fastest-path: fly vs drive)
- [x] Known flight database with schedule logic
- [x] Live flight status checking (FR24 scrape + FlightRadarAPI)
- [x] Route ranking by speed
- [x] Rich terminal display with action steps
- [x] Balanced scoring formula (wait * 1.5 + ground + flight + layover * 0.8)
- [x] Three speed modes: soonest / shortest_total / balanced
- [x] Dual timezone display (AST departure / CST arrival)
- [x] Booking links + phone numbers on every route card
- [x] Price estimates (economy + business) on route cards
- [x] `--watch` mode with auto-refresh and `[CHANGED]` alerts + bell
- [x] `[STALE]` data warnings (>15 min)
- [x] Conflict proximity scoring per route (LOW/MED/HIGH/BLOCKED)
- [x] Summary table at the top before detailed cards
- [x] All criteria exposed as CLI flags with defaults
- [x] `--sort` by score/depart/price/duration
- [x] `--max-stops`, `--max-wait`, `--hide-cancelled` filters
- [x] Offline fallback mode
- [x] Single flight status checker (`evac status CX644`)

### Phase 2 — v1.1: Price & Seat Availability
- [ ] Price scraping from official airline booking pages
- [ ] Price scraping from Google Flights / Skyscanner as fallback
- [ ] Seat availability detection (parse booking page for "sold out" / cabin class availability)
- [ ] Multi-passenger seat check (check if N seats available on same flight)
- [ ] Budget filter (hide routes above the configured cap)

### Phase 3 — v1.2: Alerts & Notifications
- [ ] SMS alerts when a route status changes (via Twilio or similar)
- [ ] WhatsApp alerts as alternative delivery channel
- [ ] Alert triggers: flight cancelled → reinstated, airspace reopened, new flight added
- [ ] Configurable alert preferences (which routes to watch, quiet hours)
- [ ] Alert cooldown to prevent spam during rapid changes

### Phase 4 — v1.3: Web UI (Mobile-First)
- [ ] Mobile-first web interface (critical — may not have laptop while evacuating)
- [ ] Same data as CLI but accessible from any phone browser
- [ ] One-tap call buttons for airline phone numbers
- [ ] One-tap booking links
- [ ] Auto-refresh with push notifications
- [ ] Offline-capable PWA (cache last known data)
- [ ] Shareable URL (send your evacuation plan to family/friends)

### Phase 5 — v1.4: Intelligence & Data Sources
- [ ] Conflict news feed integration (Al Jazeera, Reuters, BBC RSS)
- [ ] Auto-detect new airspace closures from news headlines (keyword NLP)
- [ ] Auto-update scenario airspace map when closures change
- [ ] Embassy evacuation flight integration (scrape embassy websites for charter/repatriation info)
- [ ] NOTAM feed parser (official aviation notices)
- [ ] Airport departure board scraper (verify flights are actually departing)

### Phase 6 — v1.5: Smart Predictions
- [ ] Historical pattern detection from past conflicts (2024 Iran-Israel, 2020 Soleimani, etc.)
- [ ] Predict which flights are likely to resume and when, based on patterns
- [ ] Predict airspace reopening timelines
- [ ] Suggest "wait vs go now" recommendation based on prediction confidence
- [ ] Transit visa checker per passport type (auto-check if hub transit requires visa)

### Phase 7 — v2.0: Multi-Scenario & Community
- [ ] Multiple concurrent scenarios (evacuate from different origins)
- [ ] Community-sourced flight status reports (crowdsource from other evacuees)
- [ ] Real-time chat between evacuees on same route
- [ ] Integration with ride-sharing for ground segments
- [ ] Multi-language support (Chinese, Arabic, English)
