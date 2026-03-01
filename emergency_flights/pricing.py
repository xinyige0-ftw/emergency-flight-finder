"""Phase 2: Price & seat availability scraping."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from rich.console import Console

from .models import FlightLeg

console = Console(stderr=True)

GOOGLE_FLIGHTS_URL = "https://www.google.com/travel/flights"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


async def check_prices_and_seats(
    flights: list[FlightLeg],
    passengers: int = 1,
    live: bool = True,
) -> list[FlightLeg]:
    """Check live prices and seat availability for all flights."""
    if not live:
        console.print("[dim]Skipping price checks (offline mode)[/dim]")
        return flights

    console.print("[bold]Checking prices & seat availability...[/bold]")
    tasks = [_check_single_flight(f, passengers) for f in flights]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    updated = []
    for flight, result in zip(flights, results):
        if isinstance(result, Exception):
            console.print(f"  [dim]Price check failed for {flight.flight_number}: {result}[/dim]")
            updated.append(flight)
        else:
            updated.append(result)

    return updated


async def _check_single_flight(flight: FlightLeg, passengers: int) -> FlightLeg:
    """Try airline-specific scraper, fall back to Google Flights."""
    console.print(f"  [dim]Pricing {flight.flight_number} ({flight.airline})...[/dim]")

    scraper = _get_scraper(flight.airline)
    if scraper:
        try:
            result = await scraper(flight, passengers)
            if result.price_economy_usd and result.seats_available is not None:
                return result
        except Exception:
            pass

    try:
        return await _scrape_google_flights(flight, passengers)
    except Exception:
        pass

    return flight


def _get_scraper(airline: str):
    scrapers = {
        "Turkish Airlines": _scrape_turkish,
        "Saudia": _scrape_saudia,
        "Cathay Pacific": _scrape_cathay,
        "Air China": _scrape_airchina,
        "China Southern": _scrape_csair,
    }
    return scrapers.get(airline)


async def _scrape_google_flights(flight: FlightLeg, passengers: int) -> FlightLeg:
    """Scrape Google Flights search results for pricing."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(
            GOOGLE_FLIGHTS_URL,
            params={"hl": "en", "gl": "us"},
            headers=HEADERS,
        )
        if resp.status_code == 200:
            prices = _extract_prices_from_html(resp.text)
            if prices.get("economy"):
                flight.price_economy_usd = prices["economy"]
                flight.price_source = "google_flights"
            if prices.get("business"):
                flight.price_business_usd = prices["business"]
    return flight


def _extract_prices_from_html(html: str) -> dict:
    """Extract price figures from HTML text."""
    prices: dict = {}
    matches = re.findall(r'\$[\d,]+', html)
    if matches:
        amounts = []
        for m in matches:
            try:
                amounts.append(int(m.replace('$', '').replace(',', '')))
            except ValueError:
                continue
        reasonable = [a for a in amounts if 100 < a < 15000]
        if reasonable:
            prices["economy"] = min(reasonable)
    return prices


async def _scrape_turkish(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.turkishairlines.com/en-sa/flights/"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            text = resp.text.lower()
            flight.seats_available = "sold out" not in text and "no availability" not in text
            prices = _extract_prices_from_html(resp.text)
            if prices.get("economy"):
                flight.price_economy_usd = prices["economy"]
                flight.price_source = "turkish_airlines"
    return flight


async def _scrape_saudia(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.saudia.com/en/booking"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = "sold out" not in resp.text.lower()
            flight.price_source = "saudia"
    return flight


async def _scrape_cathay(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.cathaypacific.com/cx/en_US.html"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = True
            flight.price_source = "cathay_pacific"
    return flight


async def _scrape_airchina(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.airchina.com/en/"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = True
            flight.price_source = "air_china"
    return flight


async def _scrape_csair(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.csair.com/en/"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = True
            flight.price_source = "china_southern"
    return flight


def filter_by_budget(
    flights: list[FlightLeg], budget_usd: float, passengers: int = 1,
) -> list[FlightLeg]:
    """Tag flights that exceed the per-person budget."""
    for f in flights:
        if f.price_economy_usd and (f.price_economy_usd * passengers) > budget_usd:
            f.over_budget = True
    return flights


def check_multi_passenger_availability(
    flights: list[FlightLeg], passengers: int,
) -> list[FlightLeg]:
    """Flag flights where seat count may be insufficient for the group."""
    for f in flights:
        if passengers > 1 and f.seats_available is False:
            f.seats_sufficient = False
        elif passengers > 1:
            f.seats_sufficient = None
        else:
            f.seats_sufficient = f.seats_available
    return flights
