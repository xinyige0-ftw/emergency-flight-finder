"""P1: External crowdsource — X/Twitter (Nitter RSS), Telegram RSS bridges, embassy advisories."""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus

import httpx
from rich.console import Console

console = Console(stderr=True)

HEADERS = {"User-Agent": "EmergencyFlightFinder/1.0 (evacuation tool)"}

# Nitter RSS (no API key). Use env NITTER_INSTANCE to override.
NITTER_INSTANCE = os.environ.get("NITTER_INSTANCE", "https://nitter.net")

# Search queries for evacuation-relevant tweets
TWITTER_SEARCH_QUERIES = [
    "bahrain flight cancelled OR riyadh OR dammam",
    "saudi arabia flight evacuation",
    "airspace closed gulf",
]

# Embassy / travel advisory RSS
EMBASSY_RSS = [
    ("US Travel", "https://travel.state.gov/cis/rss/cis_notice.xml"),
    ("UK FCO", "https://www.gov.uk/foreign-travel-advice/bahrain/rss"),
    ("UK FCO Saudi", "https://www.gov.uk/foreign-travel-advice/saudi-arabia/rss"),
]

# Optional: Telegram channels as RSS (user can set TELEGRAM_RSS_URLS as comma-separated)
TELEGRAM_RSS_ENV = "TELEGRAM_RSS_URLS"


class CrowdItem:
    def __init__(self, source: str, text: str, link: str = "", published: str = "", author: str = ""):
        self.source = source
        self.text = text
        self.link = link
        self.published = published
        self.author = author

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "text": self.text,
            "link": self.link,
            "published": self.published,
            "author": self.author,
        }


async def fetch_x_posts(max_items: int = 15) -> list[CrowdItem]:
    """Fetch recent X/Twitter posts via Nitter RSS (no API key)."""
    items: list[CrowdItem] = []
    base = NITTER_INSTANCE.rstrip("/")
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        for q in TWITTER_SEARCH_QUERIES[:2]:
            try:
                url = f"{base}/search/rss?f=tweets&q={quote_plus(q)}"
                r = await client.get(url, headers=HEADERS)
                if r.status_code != 200:
                    continue
                for item in _parse_rss_items(r.text, "X"):
                    items.append(item)
                    if len(items) >= max_items:
                        break
            except Exception as e:
                console.print(f"[dim]Nitter fetch failed: {e}[/dim]")
            if len(items) >= max_items:
                break
    return items[:max_items]


def _parse_rss_items(xml: str, source: str) -> list[CrowdItem]:
    out: list[CrowdItem] = []
    for entry in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL):
        title = re.search(r"<title[^>]*>(.*?)</title>", entry, re.DOTALL)
        link = re.search(r"<link[^>]*>(.*?)</link>", entry, re.DOTALL)
        link = link or re.search(r'<link[^>]*href="([^"]+)"', entry)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", entry, re.DOTALL)
        desc = re.search(r"<description[^>]*>(.*?)</description>", entry, re.DOTALL)
        text = _strip_html(desc.group(1) if desc else (title.group(1) if title else ""))
        if not text or len(text) < 10:
            continue
        out.append(CrowdItem(
            source=source,
            text=text[:400],
            link=_strip_html(link.group(1)) if link else "",
            published=pub.group(1).strip() if pub else "",
        ))
    return out[:20]


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", s)
    return s.strip()


async def fetch_telegram_via_rss(max_items: int = 10) -> list[CrowdItem]:
    """Fetch from Telegram channels if TELEGRAM_RSS_URLS (comma-separated) is set."""
    urls = os.environ.get(TELEGRAM_RSS_ENV, "").strip().split(",")
    urls = [u.strip() for u in urls if u.strip()]
    if not urls:
        return []
    items: list[CrowdItem] = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for url in urls[:5]:
            try:
                r = await client.get(url, headers=HEADERS)
                if r.status_code != 200:
                    continue
                for item in _parse_rss_items(r.text, "Telegram"):
                    items.append(item)
            except Exception as e:
                console.print(f"[dim]Telegram RSS failed: {e}[/dim]")
    return items[:max_items]


async def fetch_embassy_advisories(max_items: int = 15) -> list[CrowdItem]:
    """Fetch embassy / travel advisory RSS feeds."""
    items: list[CrowdItem] = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for name, url in EMBASSY_RSS:
            try:
                r = await client.get(url, headers=HEADERS)
                if r.status_code != 200:
                    continue
                for item in _parse_rss_items(r.text, name):
                    if any(kw in item.text.lower() for kw in ("bahrain", "saudi", "gulf", "evacuation", "flight", "travel")):
                        items.append(item)
            except Exception as e:
                console.print(f"[dim]Embassy RSS failed ({name}): {e}[/dim]")
    return items[:max_items]


async def fetch_all_crowdsource(max_per_source: int = 15) -> dict:
    """Fetch X, Telegram, and embassy sources; return combined dict for API."""
    x, tg, emb = await asyncio.gather(
        fetch_x_posts(max_per_source),
        fetch_telegram_via_rss(10),
        fetch_embassy_advisories(max_per_source),
    )
    return {
        "x": [i.to_dict() for i in x],
        "telegram": [i.to_dict() for i in tg],
        "embassy": [i.to_dict() for i in emb],
    }
