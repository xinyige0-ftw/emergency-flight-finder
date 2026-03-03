"""Flight status history tracking, trend analysis, and transit visa checks."""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from .models import FlightStatus, ReliabilityScore, Route, Scenario

console = Console(stderr=True)

HISTORY_FILE = Path.home() / ".flight_monitor_history.json"
CONFLICT_START_DATE = date(2026, 2, 28)

STATUS_LABELS = {
    "operating": "正常",
    "scheduled": "计划",
    "cancelled": "取消",
    "delayed": "延误",
    "unknown": "未知",
    "landed": "已降落",
}

CONFLICT_PATTERNS = {
    "gulf_war_1991": {
        "duration_days": 42,
        "airspace_recovery_days": 3,
        "flight_resume_pattern": "hub_first",
        "notes": "主要航司在停火后3天内恢复航班",
    },
    "iraq_2003": {
        "duration_days": 21,
        "airspace_recovery_days": 7,
        "flight_resume_pattern": "gradual",
        "notes": "区域空域在一周内分阶段重新开放",
    },
    "yemen_2015": {
        "duration_days": 365,
        "airspace_recovery_days": None,
        "flight_resume_pattern": "partial",
        "notes": "部分航线始终未完全恢复，枢纽机场保持开放",
    },
    "qatar_blockade_2017": {
        "duration_days": 1279,
        "airspace_recovery_days": 1,
        "flight_resume_pattern": "immediate",
        "notes": "解决后空域在24小时内重新开放",
    },
    "ukraine_2022": {
        "duration_days": None,
        "airspace_recovery_days": None,
        "flight_resume_pattern": "none",
        "notes": "乌克兰和俄罗斯空域对大多数航司仍然关闭",
    },
    "iran_israel_2024": {
        "duration_days": 2,
        "airspace_recovery_days": 1,
        "flight_resume_pattern": "immediate",
        "notes": "短暂关闭，降级后次日恢复航班",
    },
}

TRANSIT_VISA_RULES = {
    "CN": {
        "IST": {"required": False, "notes": "中国护照：土耳其免签过境（最长30天）"},
        "MCT": {"required": True, "notes": "中国护照：阿曼需要电子签证"},
        "BKK": {"required": False, "notes": "中国护照：泰国免签30天"},
        "SIN": {"required": False, "notes": "中国护照：新加坡免签过境96小时"},
        "KUL": {"required": False, "notes": "中国护照：马来西亚免签30天"},
        "DEL": {"required": True, "notes": "中国护照：印度需要电子签证"},
        "BOM": {"required": True, "notes": "中国护照：印度需要电子签证"},
        "LHR": {"required": True, "notes": "中国护照：英国需要过境签证（DATV）"},
        "ADD": {"required": True, "notes": "中国护照：埃塞俄比亚可落地电子签"},
        "DOH": {"required": False, "notes": "中国护照：卡塔尔免签30天（但空域关闭）"},
        "DXB": {"required": False, "notes": "中国护照：阿联酋免签30天（但空域关闭）"},
        "NRT": {"required": True, "notes": "中国护照：日本过境可能需要签证"},
        "ICN": {"required": False, "notes": "中国护照：韩国免签过境（最长72小时）"},
    },
}


_SEED_STATUS = {
    # Feb 28=Sat | Mar 1=Sun | Mar 2=Mon | Mar 3=Tue
    # Verified against flightera.net where available. Only on actual operating days.
    #
    # ── Direct China flights ──
    # CZ5008 Tue/Thu/Sat — flightera: Feb 28 "Unknown", Mar 3 cancelled (user-confirmed)
    "CZ5008":  {"2026-02-28": "unknown",                                                                       "2026-03-03": "cancelled"},
    # SV884 Tue/Thu/Sat — flightera (CZ7893): Feb 28 Landed 7h late, Mar 3 Cancelled
    "SV884":   {"2026-02-28": "delayed",                                                                        "2026-03-03": "cancelled"},
    # CX644 daily
    "CX644":   {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "cancelled",             "2026-03-03": "cancelled"},
    # CA790 Mon/Wed/Fri/Sun
    "CA790":   {                             "2026-03-01": "cancelled",  "2026-03-02": "cancelled"},                                          # Mon/Wed/Fri/Sun → Mar 3=Tue ✗
    # SV888 Sun/Wed
    "SV888":   {                             "2026-03-01": "cancelled"},
    # SV882 Mon/Wed/Fri — flightera: Mar 2 Landed on time, Mar 4 (Wed) Planned
    "SV882":   {                                                         "2026-03-02": "operating"},
    # SV886 Mon/Fri
    "SV886":   {                                                         "2026-03-02": "cancelled"},
    #
    # ── Turkish (daily, confirmed operating throughout) ──
    "TK145":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    "TK157":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    "TK170":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    "TK88":    {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    "TK26":    {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    "TK72":    {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    "TK54":    {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},
    #
    # ── Oman Air ──
    "WY667":   {"2026-02-28": "delayed",    "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "WY669":   {                             "2026-03-01": "delayed",    "2026-03-02": "operating"},                                          # Mon/Wed/Fri/Sun
    "WY841":   {"2026-02-28": "delayed",    "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "WY843":   {"2026-02-28": "cancelled",  "2026-03-01": "delayed",    "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "WY851":   {"2026-02-28": "cancelled",                                                                      "2026-03-03": "cancelled"},  # Tue/Thu/Sat
    #
    # ── SE Asia connections ──
    "CZ3036":  {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "cancelled",             "2026-03-03": "cancelled"},   # daily
    "TG668":   {"2026-02-28": "cancelled",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "TG614":   {"2026-02-28": "cancelled",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "SQ802":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "SQ830":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "MH376":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "MH388":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "SV846":   {                                                         "2026-03-02": "operating"},                                          # Mon/Wed/Fri
    "SV848":   {"2026-02-28": "cancelled",                                                                      "2026-03-03": "cancelled"},  # Tue/Thu/Sat
    "SV850":   {"2026-02-28": "cancelled",                               "2026-03-02": "cancelled"},                                          # Mon/Wed/Sat
    #
    # ── India ──
    "AI902":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "AI314":   {                             "2026-03-01": "operating",  "2026-03-02": "operating"},                                          # Mon/Wed/Fri/Sun → Mar 3=Tue ✗
    "AI348":   {"2026-02-28": "operating",  "2026-03-01": "operating",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    #
    # ── Domestic/other ──
    "SV1079":  {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "SV1085":  {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "cancelled",             "2026-03-03": "cancelled"},   # daily
    "XY402":   {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "cancelled",             "2026-03-03": "cancelled"},   # daily
    "SV1055":  {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "operating",             "2026-03-03": "operating"},   # daily
    "SV1521":  {"2026-02-28": "cancelled",  "2026-03-01": "cancelled",  "2026-03-02": "cancelled",             "2026-03-03": "cancelled"},   # daily
}


def seed_initial_history():
    """Pre-populate history for Feb 28 - Mar 2, only on days each flight actually operates.
    Overwrites seed-date entries to fix any stale data from earlier seeding."""
    history = _load_history()
    flights = history.setdefault("flights", {})
    seed_dates = set()
    for ds in _SEED_STATUS.values():
        seed_dates.update(ds.keys())

    changed = False
    # Remove stale seed entries for flights that shouldn't have data on certain dates
    for flight_number in list(flights.keys()):
        expected = _SEED_STATUS.get(flight_number, {})
        for d in list(seed_dates):
            if d in flights.get(flight_number, {}) and d not in expected:
                del flights[flight_number][d]
                changed = True

    for flight_number, date_statuses in _SEED_STATUS.items():
        flight_data = flights.setdefault(flight_number, {})
        for date_key, status in date_statuses.items():
            if flight_data.get(date_key, {}).get("status") != status:
                flight_data[date_key] = {
                    "status": status,
                    "checked_at": f"{date_key}T12:00:00+00:00",
                }
                changed = True

    if changed:
        _save_history(history)


def record_flight_status(flight_number: str, status: str, check_date: Optional[date] = None):
    """Record a single flight's status for a given date."""
    if check_date is None:
        check_date = datetime.now(timezone.utc).date()

    history = _load_history()
    flights = history.setdefault("flights", {})
    flight_data = flights.setdefault(flight_number, {})
    date_key = check_date.isoformat()

    flight_data[date_key] = {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_history(history)


def record_all_flight_statuses(routes: list[Route]):
    """Record status of every flight leg in the current route set."""
    today = datetime.now(timezone.utc).date()
    history = _load_history()
    flights = history.setdefault("flights", {})

    for route in routes:
        for leg in route.flight_legs:
            flight_data = flights.setdefault(leg.flight_number, {})
            date_key = today.isoformat()
            flight_data[date_key] = {
                "status": leg.status.value,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    _save_history(history)


def get_flight_history(flight_number: str) -> dict[str, str]:
    """Get a flight's status history since conflict start.

    Returns dict like {"2026-02-28": "cancelled", "2026-03-01": "operating", ...}
    """
    history = _load_history()
    flight_data = history.get("flights", {}).get(flight_number, {})

    result = {}
    current = CONFLICT_START_DATE
    today = datetime.now(timezone.utc).date()

    while current <= today:
        date_key = current.isoformat()
        if date_key in flight_data:
            result[date_key] = flight_data[date_key]["status"]
        current += timedelta(days=1)

    return result


def get_all_flight_histories() -> dict[str, dict[str, str]]:
    """Get status history for all tracked flights since conflict start."""
    history = _load_history()
    all_flights = history.get("flights", {})

    result = {}
    today = datetime.now(timezone.utc).date()

    for flight_number, flight_data in all_flights.items():
        flight_history = {}
        current = CONFLICT_START_DATE
        while current <= today:
            date_key = current.isoformat()
            if date_key in flight_data:
                flight_history[date_key] = flight_data[date_key]["status"]
            current += timedelta(days=1)
        if flight_history:
            result[flight_number] = flight_history

    return result


def get_daily_summary() -> list[dict]:
    """Get daily aggregate counts since conflict start.

    Returns list of {"date": "2026-02-28", "operating": 5, "cancelled": 3, "delayed": 1, ...}
    """
    history = _load_history()
    all_flights = history.get("flights", {})

    today = datetime.now(timezone.utc).date()
    current = CONFLICT_START_DATE
    summaries = []

    while current <= today:
        date_key = current.isoformat()
        counts: dict[str, int] = {}
        for flight_data in all_flights.values():
            if date_key in flight_data:
                status = flight_data[date_key]["status"]
                counts[status] = counts.get(status, 0) + 1

        if counts:
            summaries.append({
                "date": date_key,
                "total": sum(counts.values()),
                **counts,
            })
        current += timedelta(days=1)

    return summaries


def record_status_snapshot(routes: list[Route]):
    """Save current route statuses to history (legacy compatibility + new per-flight tracking)."""
    record_all_flight_statuses(routes)

    history = _load_history()
    now = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "timestamp": now,
        "routes": [
            {
                "name": r.name,
                "reliability": r.reliability.value,
                "statuses": [leg.status.value for leg in r.flight_legs],
                "score": r.score,
            }
            for r in routes
        ],
    }
    history.setdefault("snapshots", []).append(snapshot)
    if len(history["snapshots"]) > 500:
        history["snapshots"] = history["snapshots"][-500:]
    _save_history(history)


def analyze_patterns(routes: list[Route]) -> list[dict]:
    """Analyze historical data to detect per-flight trends."""
    all_histories = get_all_flight_histories()

    if not all_histories:
        return [{"type": "info", "message": "暂无历史数据，持续监控中..."}]

    insights = []
    route_flights = set()
    for r in routes:
        for leg in r.flight_legs:
            route_flights.add(leg.flight_number)

    for fn in route_flights:
        fh = all_histories.get(fn, {})
        if len(fh) < 2:
            continue

        statuses = list(fh.values())
        recent = statuses[-3:] if len(statuses) >= 3 else statuses

        cancelled_count = sum(1 for s in statuses if s == "cancelled")
        total_count = len(statuses)
        cancel_rate = cancelled_count / total_count if total_count > 0 else 0

        if all(s == "cancelled" for s in recent) and len(recent) >= 2:
            insights.append({
                "type": "trend_down",
                "flight": fn,
                "message": f"{fn}：连续{len(recent)}天取消，短期内恢复可能性低",
                "confidence": "high",
            })
        elif recent[-1] in ("operating", "landed") and recent[0] == "cancelled":
            insights.append({
                "type": "trend_up",
                "flight": fn,
                "message": f"{fn}：已恢复运营（此前曾取消）",
                "confidence": "high",
            })
        elif all(s in ("operating", "landed", "scheduled") for s in recent) and len(recent) >= 2:
            insights.append({
                "type": "stable",
                "flight": fn,
                "message": f"{fn}：稳定运营中（连续{len(recent)}天正常）",
                "confidence": "high",
            })
        elif cancel_rate > 0.5:
            insights.append({
                "type": "trend_down",
                "flight": fn,
                "message": f"{fn}：取消率 {cancel_rate:.0%}（{cancelled_count}/{total_count}天）",
                "confidence": "medium",
            })

    if not insights:
        return [{"type": "info", "message": "暂无明显趋势，持续监控中..."}]

    insights.sort(key=lambda x: {"trend_down": 0, "trend_up": 1, "stable": 2, "info": 3}.get(x["type"], 3))
    return insights


def _route_summary(route: Route) -> str:
    """Format a route as '出发 HH:MM 沙特时间 · 飞行 Xh' for display."""
    from .models import AST
    parts = []
    if route.next_departure:
        local_dep = route.next_departure.astimezone(AST)
        day_cn = {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四",
                  "Fri": "周五", "Sat": "周六", "Sun": "周日"}.get(
            local_dep.strftime("%a"), local_dep.strftime("%a"))
        parts.append(f"出发 {day_cn} {local_dep.strftime('%H:%M')} 沙特时间")
    fh = route.flight_hours
    if route.num_stops > 0:
        parts.append(f"飞行 {fh:.0f}h（{route.num_stops}次中转）")
    else:
        parts.append(f"飞行 {fh:.0f}h 直飞")
    return " · ".join(parts)


def wait_vs_go_recommendation(routes: list[Route], scenario: Scenario) -> dict:
    """Recommend whether to book now or wait."""
    viable = sorted(
        (r for r in routes if r.reliability != ReliabilityScore.LOW),
        key=lambda r: r.score,
    )

    if not viable:
        return {
            "action": "wait",
            "confidence": "low",
            "reason": "暂无确认运营的航班，请等待状态更新。",
            "check_again_hours": 2,
        }

    best = viable[0]
    high_rel = [r for r in viable if r.reliability == ReliabilityScore.HIGH]

    if high_rel and high_rel[0].score < 25:
        r = high_rel[0]
        return {
            "action": "go_now",
            "confidence": "high",
            "reason": f"确认运营中: {r.name} — {_route_summary(r)}",
            "recommended_route": r.name,
        }

    if best.total_hours < 24 and best.reliability == ReliabilityScore.MEDIUM:
        return {
            "action": "go_now",
            "confidence": "medium",
            "reason": f"最佳选择: {best.name} — {_route_summary(best)}。状态未确认，建议致电航司。",
            "recommended_route": best.name,
        }

    has_improving = any(
        r.reliability == ReliabilityScore.MEDIUM and r.total_hours < 30
        for r in viable
    )
    if has_improving and best.total_hours > 48:
        return {
            "action": "wait_short",
            "confidence": "medium",
            "reason": "24小时内可能出现更好选择，当前最快方案需48小时以上。建议持续关注。",
            "check_again_hours": 4,
        }

    return {
        "action": "go_now",
        "confidence": "medium",
        "reason": f"建议选择 {best.name} — {_route_summary(best)}",
        "recommended_route": best.name,
    }


def check_transit_visa(passport: str, hub_code: str) -> dict:
    passport = passport.upper()
    hub_code = hub_code.upper()
    rules = TRANSIT_VISA_RULES.get(passport, {})
    rule = rules.get(hub_code)
    if rule:
        return {
            "passport": passport,
            "hub": hub_code,
            "visa_required": rule["required"],
            "notes": rule["notes"],
        }
    return {
        "passport": passport,
        "hub": hub_code,
        "visa_required": None,
        "notes": f"{passport}护照在{hub_code}的过境签证规定未知，请手动查询。",
    }


def check_all_transit_visas(passport: str, routes: list[Route]) -> list[dict]:
    checked_hubs = set()
    results = []
    for route in routes:
        for leg in route.flight_legs[:-1]:
            hub = leg.destination
            if hub not in checked_hubs:
                checked_hubs.add(hub)
                results.append(check_transit_visa(passport, hub))
    return results


def get_historical_context() -> list[dict]:
    return [{"conflict": k, **v} for k, v in CONFLICT_PATTERNS.items()]


def _load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_history(data: dict):
    try:
        HISTORY_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
