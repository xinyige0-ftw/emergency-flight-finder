"""Phase 7: Community features — crowdsourced reports, ride-sharing, multi-language."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from .supabase_store import is_configured as _supabase_configured
from .supabase_store import reports_load as _reports_load_sb
from .supabase_store import reports_save as _reports_save_sb
from .supabase_store import reports_upvote as _reports_upvote_sb
from .supabase_store import rides_load as _rides_load_sb
from .supabase_store import rides_save as _rides_save_sb

console = Console(stderr=True)

REPORTS_FILE = Path.home() / ".evac_community_reports.json"

TRANSLATIONS = {
    "zh": {
        "title": "沙特回国航班监控",
        "refresh": "刷新",
        "loading": "加载中...",
        "airspace": "空域状态",
        "go_now": "建议立即行动",
        "wait": "建议观望",
        "economy": "经济舱",
        "business": "商务舱",
        "transit_visa": "过境签证",
        "trend_analysis": "趋势分析",
        "no_visa": "无需签证",
        "visa_required": "需要签证",
        "check_manually": "请手动查询",
        "seats_ok": "有座位",
        "sold_out": "已售罄",
        "seats_unknown": "座位未知",
        "operating": "正常运营",
        "scheduled": "已计划",
        "cancelled": "已取消",
        "delayed": "延误",
        "unknown": "未知",
        "landed": "已降落",
        "live_loaded": "已加载实时数据",
        "cached_data": "缓存数据",
        "next_refresh": "下次刷新",
        "confirm_airline": "航班信息变化迅速，请务必与航空公司确认。",
        "no_flights": "暂无航班数据",
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
    """Submit a crowdsourced flight/airport report (Supabase if configured, else file)."""
    d = report.to_dict()
    if _supabase_configured() and _reports_save_sb(d):
        return report
    reports = _load_reports()
    reports.append(d)
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
    """Get recent community reports (Supabase + file merge when both used)."""
    reports = _reports_load_sb() if _supabase_configured() else []
    if not reports:
        reports = _load_reports()
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - (max_age_hours * 3600)
    results = []
    for r in reversed(reports):
        try:
            ts_str = (r.get("timestamp") or "1970-01-01").replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            continue
        if ts < cutoff:
            continue
        if airport and (r.get("airport") or "").upper() != airport.upper():
            continue
        if flight and (r.get("flight") or "").upper() != flight.upper():
            continue
        results.append(CommunityReport.from_dict(r))
        if len(results) >= limit:
            break
    return results


def upvote_report(report_id: str) -> bool:
    """Upvote a community report (Supabase if configured, else file)."""
    if _supabase_configured() and _reports_upvote_sb(report_id):
        return True
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
        return cls(
            ride_id=d.get("ride_id") or d.get("id", ""),
            origin=d.get("origin", ""),
            destination=d.get("destination", ""),
            departure_time=d.get("departure_time", ""),
            seats=d.get("seats", 1),
            contact=d.get("contact", ""),
            notes=d.get("notes", ""),
            posted=d.get("posted", ""),
        )


RIDES_FILE = Path.home() / ".evac_rideshares.json"


def post_rideshare(ride: RideShare) -> RideShare:
    d = ride.to_dict()
    if _supabase_configured() and _rides_save_sb(d):
        return ride
    rides = _load_json(RIDES_FILE)
    rides.append(d)
    _save_json(RIDES_FILE, rides[-200:])
    return ride


def get_rideshares(origin: str = "", destination: str = "", limit: int = 20) -> list[RideShare]:
    rides = _rides_load_sb() if _supabase_configured() else _load_json(RIDES_FILE)
    results = []
    for r in reversed(rides):
        if origin and (r.get("origin") or "").lower() != origin.lower():
            continue
        if destination and (r.get("destination") or "").lower() != destination.lower():
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
