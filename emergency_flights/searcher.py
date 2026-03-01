"""Flight status checking via FlightRadar24 API and web scraping."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from rich.console import Console

from .models import FlightLeg, FlightStatus

console = Console(stderr=True)

FR24_FLIGHT_URL = "https://www.flightradar24.com/data/flights/{code}"
FLIGHTSTATS_URL = "https://www.flightstats.com/v2/flight-tracker/{airline}/{number}"


async def check_flight_status_fr24(flight: FlightLeg) -> FlightLeg:
    """
    Check a flight's live status by scraping FlightRadar24's flight history page.
    Updates the flight object in-place and returns it.
    """
    code = flight.flight_number.lower()
    url = FR24_FLIGHT_URL.format(code=code)

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )

            if resp.status_code != 200:
                console.print(f"[dim]FR24 returned {resp.status_code} for {flight.flight_number}[/dim]")
                return flight

            text = resp.text.lower()

            today_str = datetime.now(timezone.utc).strftime("%d %b %Y").lower()

            if "cancel" in text and today_str in text:
                flight.status = FlightStatus.CANCELLED
                flight.status_source = "flightradar24"
            elif "landed" in text and today_str in text:
                flight.status = FlightStatus.LANDED
                flight.status_source = "flightradar24"
            elif "estimated" in text or "en route" in text:
                flight.status = FlightStatus.OPERATING
                flight.status_source = "flightradar24"
            elif "scheduled" in text:
                flight.status = FlightStatus.SCHEDULED
                flight.status_source = "flightradar24"
            else:
                flight.status = FlightStatus.UNKNOWN
                flight.status_source = "flightradar24"

            flight.last_checked = datetime.now(timezone.utc)

    except httpx.TimeoutException:
        console.print(f"[yellow]Timeout checking {flight.flight_number}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Error checking {flight.flight_number}: {e}[/yellow]")

    return flight


async def check_flight_status_flightradarapi(flight: FlightLeg) -> FlightLeg:
    """Check flight status using the FlightRadarAPI Python package."""
    try:
        from FlightRadar24 import FlightRadar24API

        fr = FlightRadar24API()
        results = fr.get_flights(airline=flight.airline[:2])
        for f in results:
            if flight.flight_number.upper() in str(f).upper():
                flight.status = FlightStatus.OPERATING
                flight.status_source = "flightradar24-api"
                flight.last_checked = datetime.now(timezone.utc)
                return flight

        flight.last_checked = datetime.now(timezone.utc)

    except ImportError:
        console.print("[dim]FlightRadarAPI package not available, using web scraping[/dim]")
    except Exception as e:
        console.print(f"[dim]FlightRadarAPI error for {flight.flight_number}: {e}[/dim]")

    return flight


async def check_all_flights(flights: list[FlightLeg], live: bool = True) -> list[FlightLeg]:
    """Check status of all flights. If live=False, skip network calls."""
    if not live:
        console.print("[dim]Skipping live status checks (offline mode)[/dim]")
        return flights

    console.print("[bold]Checking live flight statuses...[/bold]")
    checked: list[FlightLeg] = []

    for flight in flights:
        console.print(f"  [dim]Checking {flight.flight_number} ({flight.airline})...[/dim]")
        updated = await check_flight_status_fr24(flight)
        if updated.status == FlightStatus.UNKNOWN:
            updated = await check_flight_status_flightradarapi(updated)
        checked.append(updated)

    return checked


def next_departure_date(flight: FlightLeg, after: Optional[datetime] = None) -> Optional[datetime]:
    """Calculate the next departure date for a flight based on its schedule."""
    if after is None:
        after = datetime.now(timezone.utc)

    if "daily" in [d.lower() for d in flight.scheduled_days]:
        return _parse_departure_today_or_tomorrow(flight, after)

    day_map = {
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    }
    scheduled_weekdays = []
    for d in flight.scheduled_days:
        key = d.lower()[:3]
        if key in day_map:
            scheduled_weekdays.append(day_map[key])

    if not scheduled_weekdays:
        return None

    current_weekday = after.weekday()
    depart_time = _parse_time(flight.depart_utc)
    if depart_time is None:
        return None

    for offset in range(8):  # check next 7 days
        candidate_day = (current_weekday + offset) % 7
        if candidate_day in scheduled_weekdays:
            candidate_date = after.date()
            from datetime import timedelta
            candidate_date = candidate_date + timedelta(days=offset)
            candidate_dt = datetime(
                candidate_date.year, candidate_date.month, candidate_date.day,
                depart_time.hour, depart_time.minute,
                tzinfo=timezone.utc,
            )
            if candidate_dt > after:
                return candidate_dt

    return None


def _parse_departure_today_or_tomorrow(flight: FlightLeg, after: datetime) -> Optional[datetime]:
    depart_time = _parse_time(flight.depart_utc)
    if depart_time is None:
        return None

    today = after.date()
    candidate = datetime(
        today.year, today.month, today.day,
        depart_time.hour, depart_time.minute,
        tzinfo=timezone.utc,
    )
    if candidate > after:
        return candidate

    from datetime import timedelta
    tomorrow = today + timedelta(days=1)
    return datetime(
        tomorrow.year, tomorrow.month, tomorrow.day,
        depart_time.hour, depart_time.minute,
        tzinfo=timezone.utc,
    )


def _parse_time(time_str: str) -> Optional[datetime]:
    """Parse a HH:MM time string, ignoring +1 day markers."""
    clean = time_str.replace("+1", "").strip()
    if not clean:
        return None
    try:
        parts = clean.split(":")
        return datetime(2000, 1, 1, int(parts[0]), int(parts[1]), tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None
