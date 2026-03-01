"""Phase 5: Intelligence — news feeds, airspace closure detection, NOTAM parsing."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from rich.console import Console

from .models import Scenario

console = Console(stderr=True)

RSS_FEEDS = [
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("FlightGlobal", "https://www.flightglobal.com/rss"),
]

AIRSPACE_KEYWORDS = [
    "airspace closed", "airspace closure", "airspace shut",
    "notam", "flight ban", "no-fly zone", "airspace restricted",
    "flights suspended", "flights grounded", "airport closed",
    "airport shut", "flights cancelled", "air traffic",
]

CONFLICT_KEYWORDS = [
    "strike", "missile", "attack", "bombing", "conflict",
    "military", "war", "invasion", "escalation", "ceasefire",
    "evacuation", "embargo", "sanctions",
]

REGION_KEYWORDS = [
    "bahrain", "saudi", "iran", "iraq", "qatar", "uae", "emirates",
    "kuwait", "oman", "yemen", "israel", "jordan", "turkey",
    "gulf", "middle east", "persian gulf", "arabian",
]

HEADERS = {
    "User-Agent": "EmergencyFlightFinder/1.0 (evacuation tool)",
}


class NewsItem:
    def __init__(self, source: str, title: str, link: str, published: str = "",
                 relevance: str = "low", tags: list[str] | None = None):
        self.source = source
        self.title = title
        self.link = link
        self.published = published
        self.relevance = relevance
        self.tags = tags or []

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "link": self.link,
            "published": self.published,
            "relevance": self.relevance,
            "tags": self.tags,
        }


async def fetch_conflict_news(max_items: int = 20) -> list[NewsItem]:
    """Fetch and filter conflict-related news from RSS feeds."""
    all_items: list[NewsItem] = []
    tasks = [_fetch_rss(name, url) for name, url in RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_items.extend(result)

    relevant = [item for item in all_items if item.relevance in ("high", "medium")]
    relevant.sort(key=lambda x: (0 if x.relevance == "high" else 1))
    return relevant[:max_items]


async def _fetch_rss(source_name: str, url: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code != 200:
                return items
            items = _parse_rss_xml(source_name, resp.text)
    except Exception as e:
        console.print(f"[dim]RSS fetch failed ({source_name}): {e}[/dim]")
    return items


def _parse_rss_xml(source: str, xml_text: str) -> list[NewsItem]:
    """Simple regex-based RSS parser (no lxml dependency)."""
    items: list[NewsItem] = []
    entries = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)
    if not entries:
        entries = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

    for entry in entries[:50]:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', entry, re.DOTALL)
        link_match = re.search(r'<link[^>]*>(.*?)</link>', entry, re.DOTALL)
        if not link_match:
            link_match = re.search(r'<link[^>]*href="([^"]+)"', entry)
        pub_match = re.search(r'<pubDate>(.*?)</pubDate>', entry, re.DOTALL)
        if not pub_match:
            pub_match = re.search(r'<published>(.*?)</published>', entry, re.DOTALL)

        title = _strip_cdata(title_match.group(1)) if title_match else ""
        link = _strip_cdata(link_match.group(1)) if link_match else ""
        published = pub_match.group(1).strip() if pub_match else ""

        if not title:
            continue

        relevance, tags = _classify_headline(title)
        if relevance != "low":
            items.append(NewsItem(
                source=source, title=title, link=link,
                published=published, relevance=relevance, tags=tags,
            ))

    return items


def _strip_cdata(text: str) -> str:
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    return text.strip()


def _classify_headline(title: str) -> tuple[str, list[str]]:
    """Classify a headline by relevance to evacuation. Returns (relevance, tags)."""
    lower = title.lower()
    tags = []

    has_region = any(kw in lower for kw in REGION_KEYWORDS)
    has_airspace = any(kw in lower for kw in AIRSPACE_KEYWORDS)
    has_conflict = any(kw in lower for kw in CONFLICT_KEYWORDS)

    if has_region:
        tags.append("region")
    if has_airspace:
        tags.append("airspace")
    if has_conflict:
        tags.append("conflict")

    if has_region and has_airspace:
        return "high", tags
    if has_region and has_conflict:
        return "high", tags
    if has_airspace:
        return "medium", tags
    if has_conflict and has_region:
        return "medium", tags

    return "low", tags


def detect_airspace_changes_from_news(
    news: list[NewsItem], scenario: Scenario,
) -> list[dict]:
    """Detect potential airspace status changes from news headlines."""
    alerts = []
    for item in news:
        if "airspace" not in item.tags:
            continue

        lower = item.title.lower()

        for country in scenario.airspace_closed:
            if country.lower() in lower and ("reopen" in lower or "resume" in lower):
                alerts.append({
                    "type": "potential_reopening",
                    "country": country,
                    "headline": item.title,
                    "source": item.source,
                    "link": item.link,
                })

        for country in scenario.airspace_open:
            if country.lower() in lower and ("close" in lower or "shut" in lower or "ban" in lower):
                alerts.append({
                    "type": "potential_closure",
                    "country": country,
                    "headline": item.title,
                    "source": item.source,
                    "link": item.link,
                })

    return alerts


async def fetch_notams(airport_codes: list[str]) -> list[dict]:
    """Fetch NOTAMs from FAA NOTAM API (public endpoint)."""
    notams: list[dict] = []
    base_url = "https://www.notams.faa.gov/dinsQueryWeb/queryRetrievalMapAction.do"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for code in airport_codes:
                resp = await client.get(
                    base_url,
                    params={"reportType": "Raw", "actionType": "notamRetrievalByICAOs",
                            "retrieveLocId": code},
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    parsed = _parse_notams(code, resp.text)
                    notams.extend(parsed)
    except Exception as e:
        console.print(f"[dim]NOTAM fetch failed: {e}[/dim]")
    return notams


def _parse_notams(airport: str, html: str) -> list[dict]:
    """Extract NOTAM text from FAA response."""
    notams = []
    blocks = re.findall(r'(A\d{4}/\d{2}.*?)(?=A\d{4}/\d{2}|$)', html, re.DOTALL)
    for block in blocks[:10]:
        clean = re.sub(r'<[^>]+>', '', block).strip()
        if not clean:
            continue
        is_critical = any(kw in clean.lower() for kw in
                         ["closed", "closure", "prohibited", "restricted", "danger area"])
        notams.append({
            "airport": airport,
            "text": clean[:500],
            "critical": is_critical,
        })
    return notams


async def scrape_airport_departures(airport_code: str) -> list[dict]:
    """Scrape departure board from FlightRadar24."""
    departures = []
    url = f"https://www.flightradar24.com/data/airports/{airport_code.lower()}/departures"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            })
            if resp.status_code == 200:
                rows = re.findall(
                    r'data-flight="([^"]+)".*?data-airline="([^"]*)".*?'
                    r'data-destination="([^"]*)".*?data-status="([^"]*)"',
                    resp.text, re.DOTALL,
                )
                for flight, airline, dest, status in rows[:30]:
                    departures.append({
                        "flight": flight,
                        "airline": airline,
                        "destination": dest,
                        "status": status,
                    })
    except Exception as e:
        console.print(f"[dim]Departure board scrape failed ({airport_code}): {e}[/dim]")
    return departures
