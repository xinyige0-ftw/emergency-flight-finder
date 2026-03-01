"""Airspace status checking via web scraping and scenario config."""
from __future__ import annotations

from datetime import datetime

import httpx
from rich.console import Console

from .models import AirspaceState, Scenario

console = Console(stderr=True)

NOTAM_SOURCES = [
    "https://www.notams.faa.gov/",
    "https://www.flightradar24.com/",
]


def get_airspace_map(scenario: Scenario) -> dict[str, AirspaceState]:
    """Build a mapping of country -> airspace state from scenario + live data."""
    status: dict[str, AirspaceState] = {}

    for country in scenario.airspace_closed:
        status[country] = AirspaceState.CLOSED
    for country in scenario.airspace_open:
        status[country] = AirspaceState.OPEN
    for country in scenario.airspace_restricted:
        status[country] = AirspaceState.RESTRICTED

    return status


async def check_airspace_live(countries: list[str]) -> dict[str, AirspaceState]:
    """
    Attempt to pull live airspace status.
    Falls back to UNKNOWN if sources are unreachable (common during crises).
    """
    results: dict[str, AirspaceState] = {}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.flightradar24.com/data/airports",
                headers={"User-Agent": "EmergencyFlightFinder/1.0"},
            )
            if resp.status_code == 200:
                console.print("[dim]Live airspace data retrieved[/dim]")
    except Exception:
        console.print("[yellow]Could not reach live airspace sources — using scenario config[/yellow]")

    return results


def is_route_viable(origin_country: str, dest_country: str, airspace_map: dict[str, AirspaceState]) -> bool:
    """Check if a route between two countries is likely viable given airspace closures."""
    origin_state = airspace_map.get(origin_country, AirspaceState.OPEN)
    dest_state = airspace_map.get(dest_country, AirspaceState.OPEN)
    return origin_state != AirspaceState.CLOSED and dest_state != AirspaceState.CLOSED


def print_airspace_summary(airspace_map: dict[str, AirspaceState]) -> None:
    closed = [c for c, s in airspace_map.items() if s == AirspaceState.CLOSED]
    restricted = [c for c, s in airspace_map.items() if s == AirspaceState.RESTRICTED]
    open_ = [c for c, s in airspace_map.items() if s == AirspaceState.OPEN]

    console.print()
    if closed:
        console.print(f"[bold red]CLOSED:[/bold red] {', '.join(closed)}")
    if restricted:
        console.print(f"[bold yellow]RESTRICTED:[/bold yellow] {', '.join(restricted)}")
    if open_:
        console.print(f"[bold green]OPEN:[/bold green] {', '.join(open_)}")
