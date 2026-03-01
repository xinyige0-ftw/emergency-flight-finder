"""P1: External crowdsource — X/Twitter (API v2 or Nitter RSS), Telegram RSS, embassy advisories."""
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

# Real X/Twitter: set TWITTER_BEARER_TOKEN for API v2 (developer.x.com). Else we use Nitter RSS.
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()

# Nitter RSS fallbacks when no API key (try in order; nitter.net often down)
NITTER_INSTANCES = [
    os.environ.get("NITTER_INSTANCE", "").strip().rstrip("/"),
    "https://nitter.poast.org",
    "https://nitter.space",
    "https://nitter.privacyredirect.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.net",
]
NITTER_INSTANCES = [b for b in NITTER_INSTANCES if b]

# Search queries for evacuation-relevant tweets
TWITTER_SEARCH_QUERIES = [
    "bahrain flight cancelled OR riyadh OR dammam",
    "saudi arabia flight evacuation",
    "airspace closed gulf",
]

# Embassy / travel advisory feeds (Atom/RSS).
# UK FCDO (Foreign, Commonwealth & Development Office): machine-readable Atom feeds, no auth.
# US State Dept blocks scrapers with CAPTCHA; add manually if you get a working endpoint.
EMBASSY_RSS = [
    ("UK FCDO Bahrain", "https://www.gov.uk/foreign-travel-advice/bahrain.atom"),
    ("UK FCDO Saudi Arabia", "https://www.gov.uk/foreign-travel-advice/saudi-arabia.atom"),
    ("UK FCDO Iran", "https://www.gov.uk/foreign-travel-advice/iran.atom"),
    ("UK FCDO Iraq", "https://www.gov.uk/foreign-travel-advice/iraq.atom"),
    ("UK FCDO UAE", "https://www.gov.uk/foreign-travel-advice/united-arab-emirates.atom"),
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


async def fetch_x_via_api(max_items: int = 15) -> list[CrowdItem]:
    """Fetch real X/Twitter posts via API v2 (developer.x.com). Requires TWITTER_BEARER_TOKEN."""
    if not TWITTER_BEARER_TOKEN:
        return []
    items: list[CrowdItem] = []
    # API query: keywords for evacuation/gulf flights (last 7 days for recent search)
    query = "bahrain OR riyadh OR dammam OR (saudi evacuation) OR (airspace closed)"
    if len(query) > 500:
        query = "bahrain flight OR riyadh OR dammam"
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": query,
        "max_results": min(max_items, 100),
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    headers = {**HEADERS, "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                console.print(f"[dim]Twitter API: {r.status_code} {r.text[:200]}[/dim]")
                return []
            data = r.json()
            users = {u["id"]: u.get("username", "?") for u in data.get("includes", {}).get("users", [])}
            for t in data.get("data", [])[:max_items]:
                text = (t.get("text") or "").strip()
                if not text or len(text) < 5:
                    continue
                author_id = t.get("author_id", "")
                username = users.get(author_id, "X")
                tweet_id = t.get("id", "")
                link = f"https://x.com/i/status/{tweet_id}" if tweet_id else ""
                created = t.get("created_at", "")
                items.append(CrowdItem(
                    source="X",
                    text=text[:400],
                    link=link,
                    published=created,
                    author=username,
                ))
    except Exception as e:
        console.print(f"[dim]Twitter API failed: {e}[/dim]")
    return items[:max_items]


async def fetch_x_via_nitter(max_items: int = 15) -> list[CrowdItem]:
    """Fetch X/Twitter posts via Nitter RSS (no API key). Tries multiple instances."""
    items: list[CrowdItem] = []
    for base in NITTER_INSTANCES:
        if not base:
            continue
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            for q in TWITTER_SEARCH_QUERIES[:2]:
                try:
                    url = f"{base}/search/rss?f=tweets&q={quote_plus(q)}"
                    r = await client.get(url, headers=HEADERS)
                    if r.status_code != 200:
                        continue
                    parsed = _parse_rss_items(r.text, "X")
                    for item in parsed:
                        items.append(item)
                        if len(items) >= max_items:
                            break
                except Exception as e:
                    console.print(f"[dim]Nitter {base}: {e}[/dim]")
                    continue
                if len(items) >= max_items:
                    break
        if items:
            break
    return items[:max_items]


async def fetch_x_posts(max_items: int = 15) -> list[CrowdItem]:
    """Fetch recent X/Twitter: real data via API if TWITTER_BEARER_TOKEN set, else Nitter RSS."""
    if TWITTER_BEARER_TOKEN:
        items = await fetch_x_via_api(max_items)
        if items:
            return items
    return await fetch_x_via_nitter(max_items)


def _parse_rss_items(xml: str, source: str) -> list[CrowdItem]:
    out: list[CrowdItem] = []
    # Support both RSS (<item>) and Atom (<entry>) feeds
    blocks = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    if not blocks:
        blocks = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    for entry in blocks:
        title = re.search(r"<title[^>]*>(.*?)</title>", entry, re.DOTALL)
        # Atom uses <link href="..."/>, RSS uses <link>url</link>
        link = re.search(r'<link[^>]+href="([^"]+)"', entry)
        if not link:
            link = re.search(r"<link[^>]*>([^<]+)</link>", entry, re.DOTALL)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", entry, re.DOTALL)
        if not pub:
            pub = re.search(r"<updated>(.*?)</updated>", entry, re.DOTALL)
        desc = re.search(r"<description[^>]*>(.*?)</description>", entry, re.DOTALL)
        if not desc:
            desc = re.search(r"<summary[^>]*>(.*?)</summary>", entry, re.DOTALL)
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
