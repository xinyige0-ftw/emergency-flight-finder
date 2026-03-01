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
        "wait_label": "Wait",
        "ground": "Ground",
        "flight": "Flight",
        "stops": "Stops",
        "economy": "Economy",
        "business": "Business",
        "score": "Score",
        "lower_better": "lower = faster escape",
        "score_tip": "Score = wait×1.5 + ground + flight + layover×0.8 + conflict penalty. Lower means you get out faster.",
        "transit_visa": "Transit Visa",
        "ground_escape": "Ground Escape",
        "trend_analysis": "Trend Analysis",
        "news": "News",
        "community": "Community",
        "intel": "Intel",
        "conflict_news": "Conflict News",
        "community_reports": "Community Reports",
        "ride_sharing": "Ride Sharing",
        "crowdsource_title": "X / Embassy / Telegram",
        "historical_patterns": "Historical Conflict Patterns",
        "no_visa": "NO VISA NEEDED",
        "visa_required": "VISA REQUIRED",
        "check_manually": "CHECK MANUALLY",
        "seats_ok": "SEATS OK",
        "sold_out": "SOLD OUT",
        "seats_unknown": "SEATS ?",
        "over_budget": "OVER BUDGET",
        "low_risk": "SAFE ROUTE",
        "low_risk_tip": "Route avoids conflict zones",
        "med_risk": "NEAR CONFLICT",
        "med_risk_tip": "Route passes near active conflict area",
        "high_risk": "CONFLICT ZONE",
        "high_risk_tip": "Route crosses active conflict airspace",
        "changed": "CHANGED",
        "live": "Live",
        "auto_off": "Auto: OFF",
        "auto_on": "Auto: ON",
        "passengers": "Passengers",
        "budget": "Budget ($)",
        "balanced": "Balanced",
        "soonest": "Soonest",
        "shortest": "Shortest",
        "best_score": "Best score",
        "departure": "Departure",
        "price": "Price",
        "duration": "Duration",
        "direct": "Direct",
        "stops_n": "stops",
        "stop_1": "stop",
        "connections": "Connections",
        "any_connections": "Any",
        "one_connection": "1 connection max",
        "nonstop_flight": "Nonstop flight",
        "confidence": "confidence",
        "high_confidence": "high confidence",
        "medium_confidence": "medium confidence",
        "low_confidence": "low confidence",
        "possible_reopening": "POSSIBLE REOPENING",
        "possible_closure": "POSSIBLE CLOSURE",
        "read_more": "Read",
        "seat_unit": "seat(s)",
        "cn_passport": "Chinese passport",
        "visa_free_transit": "visa-free transit",
        "visa_required_note": "visa required",
        "visa_unknown": "Transit visa rules unknown. Check manually.",
        "status_unconfirmed": "Status unconfirmed — call airline before leaving.",
        "waiting_risks": "Waiting risks options getting worse.",
        "no_confirmed": "No confirmed operating flights. Wait for status updates.",
        "better_options": "Better options may become available within 24h. Monitor and decide.",
        "confirmed_route": "Confirmed operating route",
        "best_option": "Best option",
        "no_reports": "No community reports yet. Be the first to report!",
        "no_rides": "No rides posted yet",
        "no_news": "No relevant conflict news found",
        "no_crowdsource": "No external feeds available",
        "loading_routes": "Loading routes...",
        "loading_news": "Loading news...",
        "collecting_data": "Collecting data...",
        "offline_cached": "OFFLINE - using cached data",
        "live_loaded": "Live data loaded",
        "cached_data": "Cached data",
        "next_refresh": "Next refresh",
        "confirm_airline": "Always confirm with the airline. Flight data changes rapidly during conflict.",
        "step_1": "Cross to Saudi via King Fahd Causeway",
        "step_2": "Fly Dammam to Riyadh (~1h15m) or drive (~4h)",
        "step_3": "Call airline to confirm flight is operating",
        "step_4": "Book fastest CONFIRMED option",
        "step_5": "Backup: Turkish Airlines via Istanbul (daily)",
        "step_6": "Passport + cash (SAR & USD) + phone charger",
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
        "wait_label": "等待时间",
        "ground": "地面交通",
        "flight": "飞行",
        "stops": "中转",
        "economy": "经济舱",
        "business": "商务舱",
        "score": "评分",
        "lower_better": "越低=越快撤离",
        "score_tip": "评分 = 等待×1.5 + 地面×1 + 飞行×1 + 中转×0.8 + 冲突区罚分。分数越低，撤离越快。",
        "transit_visa": "过境签证",
        "ground_escape": "地面撤离路线",
        "trend_analysis": "趋势分析",
        "news": "新闻",
        "community": "社区",
        "intel": "情报",
        "conflict_news": "冲突新闻",
        "community_reports": "社区报告",
        "ride_sharing": "拼车出行",
        "crowdsource_title": "X / 大使馆 / Telegram",
        "historical_patterns": "历史冲突模式",
        "no_visa": "无需签证",
        "visa_required": "需要签证",
        "check_manually": "请手动查询",
        "seats_ok": "有座位",
        "sold_out": "已售罄",
        "seats_unknown": "座位未知",
        "over_budget": "超出预算",
        "low_risk": "安全路线",
        "low_risk_tip": "航线远离冲突区域",
        "med_risk": "靠近冲突区",
        "med_risk_tip": "航线经过冲突区域附近",
        "high_risk": "冲突空域",
        "high_risk_tip": "航线穿越冲突空域",
        "changed": "已变更",
        "live": "实时",
        "auto_off": "自动: 关",
        "auto_on": "自动: 开",
        "passengers": "乘客",
        "budget": "预算 ($)",
        "balanced": "均衡",
        "soonest": "最快出发",
        "shortest": "最短总时",
        "best_score": "最优评分",
        "departure": "出发时间",
        "price": "价格",
        "duration": "飞行时长",
        "direct": "直飞",
        "stops_n": "次中转",
        "stop_1": "次中转",
        "connections": "中转次数",
        "any_connections": "不限",
        "one_connection": "最多1次中转",
        "nonstop_flight": "直飞航班",
        "confidence": "可信度",
        "high_confidence": "高可信度",
        "medium_confidence": "中等可信度",
        "low_confidence": "低可信度",
        "possible_reopening": "可能重新开放",
        "possible_closure": "可能关闭",
        "read_more": "阅读",
        "seat_unit": "个座位",
        "cn_passport": "中国护照",
        "visa_free_transit": "免签过境",
        "visa_required_note": "需要签证",
        "visa_unknown": "过境签证规定未知，请手动查询。",
        "status_unconfirmed": "状态未确认——出发前请致电航空公司确认。",
        "waiting_risks": "等待可能导致选择减少。",
        "no_confirmed": "暂无确认运营的航班。请等待状态更新。",
        "better_options": "24小时内可能出现更好的选择。持续关注并决定。",
        "confirmed_route": "已确认运营的路线",
        "best_option": "最佳选择",
        "visa_notes": {
            "IST": "中国护照：土耳其免签过境（最长30天）",
            "LHR": "中国护照：需要英国过境签证（DATV或访客签证）",
            "ADD": "中国护照：埃塞俄比亚可落地电子签",
            "DOH": "中国护照：卡塔尔免签30天",
            "DXB": "中国护照：阿联酋免签30天",
            "BKK": "中国护照：泰国免签30天",
            "SIN": "中国护照：新加坡免签过境96小时",
            "KUL": "中国护照：马来西亚免签30天",
            "DEL": "中国护照：需要印度电子签证",
            "NRT": "中国护照：日本过境可能需要签证",
            "ICN": "中国护照：韩国免签过境（最长72小时）",
        },
        "no_reports": "暂无社区报告，成为第一个报告者！",
        "no_rides": "暂无拼车信息",
        "no_news": "暂无相关冲突新闻",
        "no_crowdsource": "暂无外部信息源",
        "loading_routes": "正在加载航线...",
        "loading_news": "正在加载新闻...",
        "collecting_data": "正在收集数据...",
        "offline_cached": "离线模式 - 使用缓存数据",
        "live_loaded": "已加载实时数据",
        "cached_data": "缓存数据",
        "next_refresh": "下次刷新",
        "confirm_airline": "请务必与航空公司确认。冲突期间航班信息变化迅速。",
        "step_1": "通过法赫德国王大桥过境至沙特",
        "step_2": "从达曼飞往利雅得（约1小时15分）或自驾（约4小时）",
        "step_3": "致电航空公司确认航班运营状态",
        "step_4": "预订最快的已确认航班",
        "step_5": "备选方案：土耳其航空经伊斯坦布尔（每日）",
        "step_6": "携带护照 + 现金（沙特里亚尔和美元）+ 充电器",
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
