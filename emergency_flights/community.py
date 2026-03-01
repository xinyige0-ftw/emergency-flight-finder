"""Phase 7: Community features — crowdsourced reports, ride-sharing, multi-language."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console(stderr=True)

REPORTS_FILE = Path.home() / ".evac_community_reports.json"

TRANSLATIONS = {
    "en": {
        "title": "Emergency Flight Finder",
        "action_plan": "Action Plan",
        "departs": "Departs",
        "arrives": "Arrives",
        "book_now": "BOOK NOW",
        "call": "CALL",
        "refresh": "Refresh Now",
        "loading": "Loading...",
        "airspace": "Airspace",
        "go_now": "GO NOW",
        "wait": "WAIT",
    },
    "zh": {
        "title": "紧急航班查询",
        "action_plan": "行动计划",
        "departs": "出发",
        "arrives": "到达",
        "book_now": "立即预订",
        "call": "拨打电话",
        "refresh": "立即刷新",
        "loading": "加载中...",
        "airspace": "空域状态",
        "go_now": "立即出发",
        "wait": "等待",
    },
    "ar": {
        "title": "باحث الرحلات الطارئة",
        "action_plan": "خطة العمل",
        "departs": "المغادرة",
        "arrives": "الوصول",
        "book_now": "احجز الآن",
        "call": "اتصل",
        "refresh": "تحديث الآن",
        "loading": "جاري التحميل...",
        "airspace": "المجال الجوي",
        "go_now": "انطلق الآن",
        "wait": "انتظر",
    },
}


class CommunityReport:
    def __init__(
        self,
        report_id: str = "",
        reporter: str = "anonymous",
        report_type: str = "flight_status",
        flight_number: str = "",
        airport: str = "",
        message: str = "",
        status: str = "",
        timestamp: str = "",
        upvotes: int = 0,
    ):
        self.report_id = report_id or str(uuid.uuid4())[:8]
        self.reporter = reporter
        self.report_type = report_type
        self.flight_number = flight_number
        self.airport = airport
        self.message = message
        self.status = status
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.upvotes = upvotes

    def to_dict(self) -> dict:
        return {
            "id": self.report_id,
            "reporter": self.reporter,
            "type": self.report_type,
            "flight": self.flight_number,
            "airport": self.airport,
            "message": self.message,
            "status": self.status,
            "timestamp": self.timestamp,
            "upvotes": self.upvotes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CommunityReport:
        return cls(
            report_id=d.get("id", ""),
            reporter=d.get("reporter", "anonymous"),
            report_type=d.get("type", "flight_status"),
            flight_number=d.get("flight", ""),
            airport=d.get("airport", ""),
            message=d.get("message", ""),
            status=d.get("status", ""),
            timestamp=d.get("timestamp", ""),
            upvotes=d.get("upvotes", 0),
        )


def submit_report(report: CommunityReport) -> CommunityReport:
    """Submit a crowdsourced flight/airport report."""
    reports = _load_reports()
    reports.append(report.to_dict())
    if len(reports) > 1000:
        reports = reports[-1000:]
    _save_reports(reports)
    return report


def get_reports(
    airport: str = "",
    flight: str = "",
    max_age_hours: float = 24,
    limit: int = 50,
) -> list[CommunityReport]:
    """Get recent community reports, optionally filtered."""
    reports = _load_reports()
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - (max_age_hours * 3600)

    results = []
    for r in reversed(reports):
        try:
            ts = datetime.fromisoformat(r["timestamp"]).timestamp()
        except Exception:
            continue
        if ts < cutoff:
            continue
        if airport and r.get("airport", "").upper() != airport.upper():
            continue
        if flight and r.get("flight", "").upper() != flight.upper():
            continue
        results.append(CommunityReport.from_dict(r))
        if len(results) >= limit:
            break

    return results


def upvote_report(report_id: str) -> bool:
    """Upvote a community report to signal agreement."""
    reports = _load_reports()
    for r in reports:
        if r.get("id") == report_id:
            r["upvotes"] = r.get("upvotes", 0) + 1
            _save_reports(reports)
            return True
    return False


class RideShare:
    def __init__(
        self,
        ride_id: str = "",
        origin: str = "",
        destination: str = "",
        departure_time: str = "",
        seats: int = 1,
        contact: str = "",
        notes: str = "",
        posted: str = "",
    ):
        self.ride_id = ride_id or str(uuid.uuid4())[:8]
        self.origin = origin
        self.destination = destination
        self.departure_time = departure_time
        self.seats = seats
        self.contact = contact
        self.notes = notes
        self.posted = posted or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.ride_id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_time": self.departure_time,
            "seats": self.seats,
            "contact": self.contact,
            "notes": self.notes,
            "posted": self.posted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RideShare:
        return cls(**{k: d.get(k, "") for k in
                      ["ride_id", "origin", "destination", "departure_time",
                       "seats", "contact", "notes", "posted"]})


RIDES_FILE = Path.home() / ".evac_rideshares.json"


def post_rideshare(ride: RideShare) -> RideShare:
    rides = _load_json(RIDES_FILE)
    rides.append(ride.to_dict())
    _save_json(RIDES_FILE, rides[-200:])
    return ride


def get_rideshares(origin: str = "", destination: str = "", limit: int = 20) -> list[RideShare]:
    rides = _load_json(RIDES_FILE)
    results = []
    for r in reversed(rides):
        if origin and r.get("origin", "").lower() != origin.lower():
            continue
        if destination and r.get("destination", "").lower() != destination.lower():
            continue
        results.append(RideShare.from_dict(r))
        if len(results) >= limit:
            break
    return results


def get_translations(lang: str = "en") -> dict:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])


def list_scenarios_available(scenarios_dir: Path) -> list[dict]:
    """List all available scenario YAML files."""
    if not scenarios_dir.exists():
        return []
    return [
        {"name": f.stem, "path": str(f)}
        for f in sorted(scenarios_dir.glob("*.yaml"))
    ]


def _load_reports() -> list[dict]:
    return _load_json(REPORTS_FILE)


def _save_reports(data: list[dict]):
    _save_json(REPORTS_FILE, data)


def _load_json(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return []


def _save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
