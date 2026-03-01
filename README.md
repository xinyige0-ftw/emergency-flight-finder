# Emergency Flight Finder

Find the fastest way out of a conflict zone by air.

This tool was built during an active regional conflict to help people evacuate when normal flight booking tools are useless — airports closed, airspace shut, airlines cancelling without notice.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/xinyige0-ftw/emergency-flight-finder)

## Web UI (Mobile-First)

Access from any phone or browser — no install needed.

```bash
# Run locally
evac serve

# Or deploy to the cloud (see Deploy to Render button above)
```

## What it does

1. **Reads a scenario file** describing your situation: where you are, where you need to go, which airspaces are closed, which airports are reachable, and what flights normally operate
2. **Checks live flight statuses** via FlightRadar24 to see what's actually flying vs cancelled
3. **Plans complete escape routes** including ground transport (border crossings, drives) + flights (direct and connecting)
4. **Ranks everything by speed** — fastest option first, with reliability as a tiebreaker
5. **Displays actionable results** with flight numbers, departure times, airline phone numbers, and step-by-step instructions

## Quick Start

```bash
cd emergency-flight-finder
pip install -e .

# Run with the default scenario
evac find

# Run with a specific scenario
evac find -s bahrain_to_china

# Run offline (skip live flight checks)
evac find --offline

# Check a single flight's status
evac status CX644
evac status SV884
```

## Creating a Scenario

Scenarios are YAML files in the `scenarios/` directory. See `scenarios/bahrain_to_china.yaml` for a complete example.

A scenario defines:
- **Origin**: where you are (city, airport, whether it's closed)
- **Destination**: where you need to go (country, preferred cities)
- **Escape routes**: ground/sea segments to reach an operational airport
- **Operational airports**: airports you can realistically get to that are still open
- **Safe hubs**: connection airports in unaffected countries
- **Airspace status**: which countries are open/closed/restricted
- **Known flights**: specific flights with schedules, so the tool can check their status and calculate timing

## How Ranking Works

Routes are ranked by:
1. **Reliability** — confirmed operating flights beat scheduled/unknown ones
2. **Total time** — including wait time until departure, ground transport, flight time, and layovers
3. Cancelled flights are shown last (in case they get reinstated)

## Limitations

- Flight status checks depend on FlightRadar24 being reachable — during major conflicts, even tracking sites may be slow
- Schedule data in scenarios is manually curated — airlines can change schedules without notice
- This is a planning tool, not a booking engine — you still need to call the airline or book online
- Always confirm with the airline before heading to the airport
