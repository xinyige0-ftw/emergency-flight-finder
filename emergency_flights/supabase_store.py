"""P1: Supabase persistence for community reports and rides (when SUPABASE_URL + key set)."""
from __future__ import annotations

import os
from typing import Optional

_REPORT_TABLE = "evac_reports"
_RIDES_TABLE = "evac_rides"


def _client():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def reports_load() -> list[dict]:
    """Load reports from Supabase or return [] if not configured/fail."""
    c = _client()
    if not c:
        return []
    try:
        r = c.table(_REPORT_TABLE).select("*").order("timestamp", desc=True).limit(500).execute()
        return [{"id": x.get("id"), "reporter": x.get("reporter", "anonymous"), "type": x.get("type", "flight_status"),
                 "flight": x.get("flight", ""), "airport": x.get("airport", ""), "message": x.get("message", ""),
                 "status": x.get("status", ""), "timestamp": x.get("timestamp", ""), "upvotes": x.get("upvotes", 0)} for x in (r.data or [])]
    except Exception:
        return []


def reports_save(report: dict) -> bool:
    """Insert one report. Returns True if saved to Supabase."""
    c = _client()
    if not c:
        return False
    try:
        c.table(_REPORT_TABLE).insert(report).execute()
        return True
    except Exception:
        return False


def reports_upvote(report_id: str) -> bool:
    """Increment upvotes for report_id. Returns True if updated."""
    c = _client()
    if not c:
        return False
    try:
        r = c.table(_REPORT_TABLE).select("upvotes").eq("id", report_id).execute()
        if not r.data or len(r.data) == 0:
            return False
        new_count = (r.data[0].get("upvotes") or 0) + 1
        c.table(_REPORT_TABLE).update({"upvotes": new_count}).eq("id", report_id).execute()
        return True
    except Exception:
        return False


def rides_load() -> list[dict]:
    """Load rides from Supabase or return [] if not configured/fail."""
    c = _client()
    if not c:
        return []
    try:
        r = c.table(_RIDES_TABLE).select("*").order("posted", desc=True).limit(200).execute()
        return [{"id": x.get("id"), "origin": x.get("origin", ""), "destination": x.get("destination", ""),
                 "departure_time": x.get("departure_time", ""), "seats": x.get("seats", 1),
                 "contact": x.get("contact", ""), "notes": x.get("notes", ""), "posted": x.get("posted", "")} for x in (r.data or [])]
    except Exception:
        return []


def rides_save(ride: dict) -> bool:
    """Insert one ride. Returns True if saved to Supabase."""
    c = _client()
    if not c:
        return False
    try:
        c.table(_RIDES_TABLE).insert(ride).execute()
        return True
    except Exception:
        return False


def is_configured() -> bool:
    return _client() is not None
