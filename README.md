# Emergency Flight Finder

**Find the fastest way out of a conflict zone by air.**

Built during the Feb 2026 Iran conflict to help people evacuate when normal booking tools are useless — airports closed, airspace shut, airlines cancelling without notice.

---

## Live

**[emergency-flight-finder.vercel.app](https://emergency-flight-finder.vercel.app)**

Open from any phone or browser. No install needed. Works offline (shows last known data).

---

## What It Does

| Feature | Details |
|---|---|
| **Route ranking** | Scores every possible escape route by total door-to-door time, penalising long pre-departure waits more than layovers |
| **Live flight status** | Checks FlightRadar24 for each known flight — operating / scheduled / cancelled / delayed |
| **Real prices** | Scrapes airline booking pages + Google Flights fallback; shows economy and business class |
| **Seat availability** | Detects if seats are available and tags routes SEATS OK / SOLD OUT / UNKNOWN |
| **Budget filter** | Hides or tags flights over your configured budget; defaults to $10,000 |
| **Conflict news** | Live RSS from Al Jazeera, Reuters, BBC, FlightGlobal — auto-detects airspace change keywords |
| **NOTAMs** | Fetches aviation notices for departure airports (RUH, JED, DMM, IST) |
| **Smart predictions** | "Wait vs Go Now" recommendation based on 7 historical conflict patterns |
| **Visa checker** | Tells you if your passport needs a transit visa at each hub (CN passport pre-configured) |
| **Embassy advisories** | UK FCDO travel advisories for the region via Atom RSS |
| **X / Twitter posts** | Real posts via Twitter API v2 (or Nitter RSS fallback) |
| **WhatsApp alerts** | Twilio-powered alerts when route status changes |
| **Multi-language** | English and Chinese (中文) throughout |
| **Offline PWA** | Service worker caches last data; add to home screen for app-like experience |

---

## Scoring Formula

```
score = (wait_hours × 1.5) + ground_hours + flight_hours + (layover_hours × 0.8) + conflict_penalty
```

Lower is better. Pre-departure wait is penalised more than layovers because in a conflict, every hour before you are airborne is higher risk.

---

## Scenario: Bahrain → China (Feb 2026)

- **Origin:** Bahrain — airspace **CLOSED**
- **Ground escape:** King Fahd Causeway (1.5h) → Dammam, Saudi Arabia
- **Departure airports:** DMM / RUH / JED
- **Routes ranked:** Direct to China + via Istanbul (Turkish Airlines, lowest risk)
- **Risk avoided:** Iran, Iraq, Qatar, UAE airspace

---

## Run Locally

```bash
git clone https://github.com/xinyige0-ftw/emergency-flight-finder
cd emergency-flight-finder
pip install -e .

# Web UI (recommended)
evac serve
# Open http://localhost:8000

# CLI
evac find
evac find --watch                    # auto-refresh every 5 min
evac find --sort price --max-stops 1
evac status TK145                    # check a single flight
```

### Environment variables (optional)

Copy `.env.example` to `.env` and fill in what you need:

```bash
# WhatsApp / SMS alerts
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1...
EVAC_ALERT_WHATSAPP=whatsapp:+86...

# Real X/Twitter posts
TWITTER_BEARER_TOKEN=...

# Persistent community data
SUPABASE_URL=...
SUPABASE_KEY=...
```

---

## Deploy

**Vercel (recommended — already configured)**

Push to `main` → auto-deploys. The `vercel.json` and `api/index.py` are already set up.

**Render**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/xinyige0-ftw/emergency-flight-finder)

**Docker**

```bash
docker build -t evac .
docker run -p 8000:8000 evac
```

---

## CLI Reference

```bash
evac find                            # run with default scenario
evac find -s bahrain_to_china        # specify scenario
evac find --offline                  # skip live checks
evac find --watch                    # auto-refresh
evac find --refresh-interval 2       # refresh every 2 min
evac find --sort price               # sort by price
evac find --max-stops 1              # max 1 connection
evac find --passengers 2             # 2 passengers
evac find --budget 5000              # $5,000 cap
evac status CX644                    # check single flight
evac list-scenarios                  # show available scenarios
```

---

## Creating Your Own Scenario

Add a YAML file to `scenarios/`. See `scenarios/bahrain_to_china.yaml` for the full structure. A scenario defines:

- Origin location and whether its airport is open
- Ground escape segments (border crossings, drives)
- Operational airports you can reach
- Safe hub airports for connections
- Airspace status map
- Known flights with schedules

---

## Limitations

- Flight status depends on FlightRadar24 being reachable (may be slow during major conflicts)
- Schedule data is manually curated — confirm with airline before heading to the airport
- Price scraping is best-effort — airline websites change their HTML frequently
- SMS alerts require US A2P 10DLC registration; WhatsApp works without it
- Community data is ephemeral on Vercel without Supabase configured
