"""Phase 2: Price & seat availability — Google Flights route-specific scraping + airline scrapers."""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import httpx
from rich.console import Console

from .models import FlightLeg

console = Console(stderr=True)

PRICE_API_URL = os.environ.get("PRICE_API_URL", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

AIRPORT_CITY = {
    "RUH": "Riyadh", "JED": "Jeddah", "DMM": "Dammam",
    "IST": "Istanbul", "PEK": "Beijing", "PVG": "Shanghai",
    "CAN": "Guangzhou", "SZX": "Shenzhen", "HKG": "Hong Kong",
}


async def _fetch_price_api(flights: list[FlightLeg]) -> dict[str, dict]:
    if not PRICE_API_URL:
        return {}
    try:
        payload = [{"flight_number": f.flight_number, "origin": f.origin, "destination": f.destination} for f in flights]
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(PRICE_API_URL, json={"flights": payload})
            if r.status_code != 200:
                return {}
            data = r.json()
            return {str(p.get("flight_number", "")).upper(): p for p in (data.get("prices") or []) if p.get("flight_number")}
    except Exception as e:
        console.print(f"[dim]Price API failed: {e}[/dim]")
        return {}


async def check_prices_and_seats(
    flights: list[FlightLeg],
    passengers: int = 1,
    live: bool = True,
) -> list[FlightLeg]:
    if not live:
        return flights

    console.print("[bold]Checking prices & seat availability...[/bold]")
    api_prices = await _fetch_price_api(flights)
    for f in flights:
        key = f.flight_number.upper()
        if key in api_prices:
            p = api_prices[key]
            if p.get("price_economy_usd") is not None:
                f.price_economy_usd = float(p["price_economy_usd"])
            if p.get("price_business_usd") is not None:
                f.price_business_usd = float(p["price_business_usd"])
            if p.get("seats_available") is not None:
                f.seats_available = bool(p["seats_available"])
            f.price_source = p.get("source") or "price_api"

    tasks = [_check_single_flight(f, passengers) for f in flights]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out = []
    for flight, result in zip(flights, results):
        if isinstance(result, Exception):
            out.append(flight)
        else:
            out.append(result)
    return out


async def _check_single_flight(flight: FlightLeg, passengers: int) -> FlightLeg:
    if flight.price_source == "price_api":
        return flight

    try:
        result = await _scrape_google_flights_route(flight, passengers)
        if result.price_source:
            return result
    except Exception:
        pass

    scraper = _get_scraper(flight.airline)
    if scraper:
        try:
            return await scraper(flight, passengers)
        except Exception:
            pass

    return flight


def _get_scraper(airline: str):
    return {
        "Turkish Airlines": _scrape_turkish,
        "Saudia": _scrape_saudia,
        "Cathay Pacific": _scrape_cathay,
        "Air China": _scrape_airchina,
        "China Southern": _scrape_csair,
    }.get(airline)


def _next_date_str(flight: FlightLeg) -> str:
    """Get next departure date as YYYY-MM-DD for Google Flights URL."""
    now = datetime.now(timezone.utc)
    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    if "daily" in [d.lower() for d in flight.scheduled_days]:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    for offset in range(7):
        candidate = now + timedelta(days=offset + 1)
        for d in flight.scheduled_days:
            if day_map.get(d.lower()[:3]) == candidate.weekday():
                return candidate.strftime("%Y-%m-%d")
    return (now + timedelta(days=1)).strftime("%Y-%m-%d")


async def _scrape_google_flights_route(flight: FlightLeg, passengers: int) -> FlightLeg:
    """Scrape Google Flights with a real origin→destination+date query."""
    origin = AIRPORT_CITY.get(flight.origin, flight.origin)
    dest = AIRPORT_CITY.get(flight.destination, flight.destination)
    date = _next_date_str(flight)
    q = f"Flights from {origin} to {dest} on {date} one way {passengers} passenger"
    url = f"https://www.google.com/travel/flights?q={quote_plus(q)}&curr=USD"

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            return flight
        text = resp.text
        prices = _extract_prices(text)
        if prices:
            flight.price_economy_usd = prices[0]
            flight.price_source = "google_flights"
            if len(prices) > 1:
                flight.price_business_usd = prices[-1]
        sold_lower = text.lower()
        if "no flights found" in sold_lower or "no results" in sold_lower:
            flight.seats_available = False
        elif prices:
            flight.seats_available = True
    return flight


def _extract_prices(html: str) -> list[float]:
    matches = re.findall(r'(?:USD|US\$|\$)\s?[\d,]+', html)
    amounts = []
    for m in matches:
        try:
            num = int(re.sub(r'[^\d]', '', m))
            if 50 < num < 20000:
                amounts.append(float(num))
        except ValueError:
            continue
    amounts = sorted(set(amounts))
    return amounts


async def _scrape_turkish(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.turkishairlines.com/en-sa/flights/"
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = "sold out" not in resp.text.lower()
            prices = _extract_prices(resp.text)
            if prices:
                flight.price_economy_usd = prices[0]
                flight.price_source = "turkish_airlines"
    return flight


async def _scrape_saudia(flight: FlightLeg, passengers: int) -> FlightLeg:
    url = "https://www.saudia.com/en/booking"
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = "sold out" not in resp.text.lower()
            flight.price_source = "saudia"
    return flight


async def _scrape_cathay(flight: FlightLeg, passengers: int) -> FlightLeg:
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        resp = await client.get("https://www.cathaypacific.com/cx/en_US.html", headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = True
            flight.price_source = "cathay_pacific"
    return flight


async def _scrape_airchina(flight: FlightLeg, passengers: int) -> FlightLeg:
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        resp = await client.get("https://www.airchina.com/en/", headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = True
            flight.price_source = "air_china"
    return flight


async def _scrape_csair(flight: FlightLeg, passengers: int) -> FlightLeg:
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        resp = await client.get("https://www.csair.com/en/", headers=HEADERS)
        if resp.status_code == 200:
            flight.seats_available = True
            flight.price_source = "china_southern"
    return flight


def filter_by_budget(
    flights: list[FlightLeg], budget_usd: float, passengers: int = 1,
) -> list[FlightLeg]:
    for f in flights:
        f.over_budget = bool(f.price_economy_usd and (f.price_economy_usd * passengers) > budget_usd)
    return flights


def check_multi_passenger_availability(
    flights: list[FlightLeg], passengers: int,
) -> list[FlightLeg]:
    for f in flights:
        if passengers > 1 and f.seats_available is False:
            f.seats_sufficient = False
        elif passengers > 1:
            f.seats_sufficient = None
        else:
            f.seats_sufficient = f.seats_available
    return flights
