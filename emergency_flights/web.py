"""FastAPI web server — 沙特回国航班监控 (Saudi-to-China Flight Monitor)."""
from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .alerts import AlertConfig, detect_changes, send_alerts, _send_twilio_whatsapp, _send_twilio_sms, _save_subscriptions
from .crowdsource import fetch_all_crowdsource
from .community import get_translations, list_scenarios_available
from .config import load_scenario
from .intel import fetch_conflict_news, detect_airspace_changes_from_news, fetch_notams
from .models import AST, CST, Route
from .predictions import (
    analyze_patterns, check_all_transit_visas, get_historical_context,
    record_status_snapshot, wait_vs_go_recommendation,
    get_all_flight_histories, get_daily_summary,
)
from .pricing import check_prices_and_seats, filter_by_budget, check_multi_passenger_availability
from .routes import build_routes
from .searcher import check_all_flights

app = FastAPI(title="沙特回国航班监控")

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
STATIC_DIR = Path(__file__).parent.parent / "static"

_previous_routes: list[Route] = []

_rate_limit: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX = 10


def _rate_limit_check(ip: str) -> bool:
    now = time.time()
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit[ip].append(now)
    return True


def _client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or request.client.host or "unknown").split(",")[0].strip()


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/sw.js")
async def service_worker():
    sw_path = STATIC_DIR / "sw.js"
    return HTMLResponse(sw_path.read_text(), media_type="application/javascript")


@app.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "name": "沙特回国航班监控",
        "short_name": "回国航班",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f8f9fa",
        "theme_color": "#1a73e8",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
    })


@app.get("/icon.svg")
async def icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="20" fill="#1a73e8"/>
    <text x="50" y="68" text-anchor="middle" fill="white" font-size="46" font-family="Arial">✈</text>
    </svg>'''
    return HTMLResponse(content=svg, media_type="image/svg+xml")


@app.get("/api/routes")
async def get_routes(
    scenario: str = "saudi_to_china",
    live: bool = False,
    speed: str = "balanced",
    budget: float = 15000,
    passengers: int = 1,
    passport: str = "CN",
    risk: str = "moderate",
    sort_by: str = "score",
    max_stops: int = 2,
    max_wait: float = 72,
    show_cancelled: bool = True,
):
    global _previous_routes
    now = datetime.now(timezone.utc)

    path = SCENARIOS_DIR / f"{scenario}.yaml"
    if not path.exists():
        return JSONResponse({"error": f"场景 '{scenario}' 未找到"}, status_code=404)

    sc = load_scenario(path)
    sc.user.passengers = passengers
    sc.user.passport = passport
    sc.user.budget_usd = budget
    sc.user.risk_tolerance = risk

    if live:
        try:
            sc.known_flights = await check_all_flights(sc.known_flights, live=True)
            sc.known_flights = await check_prices_and_seats(
                sc.known_flights, passengers=passengers, live=True,
            )
            sc.known_flights = filter_by_budget(sc.known_flights, budget, passengers)
            sc.known_flights = check_multi_passenger_availability(sc.known_flights, passengers)
        except Exception:
            pass

    routes = build_routes(sc, now=now, previous_routes=_previous_routes or None,
                          speed_mode=speed, max_stops=max_stops, max_wait_hours=max_wait)

    if not show_cancelled:
        routes = [r for r in routes if r.reliability.value != "low"]

    if sort_by == "depart":
        routes.sort(key=lambda r: r.next_departure or datetime.max.replace(tzinfo=timezone.utc))
    elif sort_by == "price":
        routes.sort(key=lambda r: r.price_economy_usd or 99999)
    elif sort_by == "duration":
        routes.sort(key=lambda r: r.flight_hours)

    alert_config = AlertConfig()
    changes = []
    if _previous_routes and alert_config.is_configured:
        changes = detect_changes(routes, _previous_routes)
        if changes:
            await send_alerts(changes, alert_config)

    record_status_snapshot(routes)
    recommendation = wait_vs_go_recommendation(routes, sc)
    visa_checks = check_all_transit_visas(passport, routes)
    patterns = analyze_patterns(routes)
    flight_histories = get_all_flight_histories()

    _previous_routes = routes

    result = {
        "updated": now.isoformat(),
        "updated_ast": now.astimezone(AST).strftime("%m-%d %H:%M 沙特时间"),
        "updated_cst": now.astimezone(CST).strftime("%m-%d %H:%M 北京时间"),
        "scenario": sc.name,
        "conflict_start": sc.conflict_start,
        "airspace": {
            "closed": sc.airspace_closed,
            "open": sc.airspace_open,
            "restricted": sc.airspace_restricted,
        },
        "airports": [
            {"code": a.code, "name": a.name, "city": a.city, "status": a.status.value, "notes": a.notes}
            for a in sc.operational_airports
        ],
        "routes": [_route_to_dict(r, now, flight_histories) for r in routes],
        "recommendation": recommendation,
        "visa_checks": visa_checks,
        "patterns": patterns,
        "daily_summary": get_daily_summary(),
    }
    return JSONResponse(result)


@app.get("/api/flight-history")
async def get_flight_history_api():
    """Per-flight status history since conflict start."""
    histories = get_all_flight_histories()
    summary = get_daily_summary()
    return JSONResponse({
        "flights": histories,
        "daily_summary": summary,
    })


@app.get("/api/history")
async def get_history():
    return JSONResponse({"conflicts": get_historical_context()})


@app.get("/api/crowdsource")
async def get_crowdsource():
    try:
        data = await fetch_all_crowdsource(max_per_source=15)
    except Exception:
        data = {"x": [], "telegram": [], "embassy": []}
    return JSONResponse(data)


@app.get("/api/news")
async def get_news(scenario: str = "saudi_to_china"):
    path = SCENARIOS_DIR / f"{scenario}.yaml"
    sc = load_scenario(path) if path.exists() else None

    try:
        news = await fetch_conflict_news(max_items=20)
    except Exception:
        news = []

    airspace_alerts = []
    if sc and news:
        airspace_alerts = detect_airspace_changes_from_news(news, sc)

    return JSONResponse({
        "news": [n.to_dict() for n in news],
        "airspace_alerts": airspace_alerts,
    })


@app.get("/api/notams")
async def get_notams(airports: str = "RUH,JED,DMM"):
    codes = [c.strip().upper() for c in airports.split(",") if c.strip()]
    try:
        notams = await fetch_notams(codes)
    except Exception:
        notams = []
    return JSONResponse({"notams": notams})


@app.get("/api/scenarios")
async def list_scenarios():
    return JSONResponse({"scenarios": list_scenarios_available(SCENARIOS_DIR)})


@app.post("/api/alerts/test")
async def api_test_alert(request: Request):
    ip = _client_ip(request)
    if not _rate_limit_check(ip):
        return JSONResponse({"ok": False, "error": "请求过多，请稍后再试"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "无效的JSON"}, status_code=400)

    phone = (body.get("phone") or "").strip().replace(" ", "")[:20]
    channel = (body.get("channel") or "whatsapp").strip()

    if not phone or not phone.startswith("+"):
        return JSONResponse({"ok": False, "error": "手机号必须以+开头，包含国家代码（如 +8613812345678）"}, status_code=400)

    config = AlertConfig()
    if not config.twilio_sid or not config.twilio_token:
        return JSONResponse({"ok": False, "error": "服务器未配置Twilio。请设置TWILIO_ACCOUNT_SID和TWILIO_AUTH_TOKEN。"}, status_code=500)

    if channel == "whatsapp" and not config.twilio_whatsapp_from:
        return JSONResponse({"ok": False, "error": "WhatsApp发送号未配置。"}, status_code=500)

    msg = "【沙特回国航班监控】测试消息：当航班状态变化（取消、延误、恢复运营）或价格变动时，您将收到实时通知。"

    try:
        if channel == "whatsapp":
            await _send_twilio_whatsapp(config, phone, msg)
        else:
            await _send_twilio_sms(config, phone, msg)
        return JSONResponse({"ok": True, "message": f"测试{channel}已发送至{phone}"})
    except Exception as e:
        err = str(e).strip()[:300]
        return JSONResponse({"ok": False, "error": err}, status_code=500)


@app.post("/api/alerts/subscribe")
async def api_subscribe_alerts(request: Request):
    ip = _client_ip(request)
    if not _rate_limit_check(ip):
        return JSONResponse({"ok": False, "error": "请求过多"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "无效的JSON"}, status_code=400)

    phone = (body.get("phone") or "").strip()[:20]
    if not phone or not phone.startswith("+"):
        return JSONResponse({"ok": False, "error": "手机号必须以+开头"}, status_code=400)

    _save_subscriptions({"whatsapp": phone})
    os.environ["EVAC_ALERT_WHATSAPP"] = phone
    return JSONResponse({"ok": True, "message": f"已订阅，航班变化时将通过WhatsApp通知{phone}"})


@app.get("/api/translations")
async def api_translations(lang: str = "zh"):
    return JSONResponse(get_translations(lang))


AIRPORT_TZ = {
    "DMM": 3, "RUH": 3, "JED": 3,
    "IST": 3, "MCT": 4,
    "PEK": 8, "PVG": 8, "CAN": 8, "SZX": 8, "HKG": 8,
    "CTU": 8, "XIY": 8, "KMG": 8, "XMN": 8,
    "BKK": 7, "SIN": 8, "KUL": 8,
    "DEL": 5.5, "BOM": 5.5,
    "ADD": 3, "LHR": 0, "CAI": 2,
    "NRT": 9, "ICN": 9, "DOH": 3, "DXB": 4,
}

TZ_LABEL = {
    3: "沙特", 4: "阿曼", 8: "北京", 0: "伦敦",
    5.5: "印度", 7: "泰国", 9: "日本", 2: "开罗",
}


def _utc_time_to_local(utc_time_str: str, tz_offset: float) -> str:
    if not utc_time_str:
        return ""
    plus_day = "+1" in utc_time_str
    clean = utc_time_str.replace("+1", "").strip()
    try:
        parts = clean.split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return utc_time_str
    total_min = h * 60 + m + int(tz_offset * 60)
    if plus_day:
        total_min += 24 * 60
    day_offset = 0
    while total_min >= 24 * 60:
        total_min -= 24 * 60
        day_offset += 1
    while total_min < 0:
        total_min += 24 * 60
        day_offset -= 1
    lh, lm = divmod(total_min, 60)
    label = TZ_LABEL.get(tz_offset, f"UTC+{tz_offset:g}")
    day_tag = f"+{day_offset}天" if day_offset > 0 else ""
    return f"{lh:02d}:{lm:02d} {label}{day_tag}"


def _route_to_dict(route: Route, now: datetime, flight_histories: dict) -> dict:
    wait = 0.0
    if route.next_departure:
        wait = max(0, (route.next_departure - now).total_seconds() / 3600)

    any_over_budget = any(leg.over_budget for leg in route.flight_legs)
    seats_statuses = [leg.seats_available for leg in route.flight_legs]
    if all(s is True for s in seats_statuses) and seats_statuses:
        seats_status = "ok"
    elif any(s is False for s in seats_statuses):
        seats_status = "sold_out"
    else:
        seats_status = "unknown"

    legs_data = []
    for idx, leg in enumerate(route.flight_legs):
        origin_tz = AIRPORT_TZ.get(leg.origin, 3)
        dest_tz = AIRPORT_TZ.get(leg.destination, 8)
        depart_local = _utc_time_to_local(leg.depart_utc, origin_tz)
        arrive_local = _utc_time_to_local(leg.arrive_utc, dest_tz)

        layover_before = None
        if idx > 0 and idx - 1 < len(route.layover_hours):
            layover_before = route.layover_hours[idx - 1]

        leg_history = flight_histories.get(leg.flight_number, {})

        legs_data.append({
            "flight": leg.flight_number,
            "airline": leg.airline,
            "from": leg.origin,
            "to": leg.destination,
            "depart_utc": leg.depart_utc,
            "arrive_utc": leg.arrive_utc,
            "depart_local": depart_local,
            "arrive_local": arrive_local,
            "duration": leg.duration_hours,
            "status": leg.status.value,
            "aircraft": leg.aircraft,
            "seats_available": leg.seats_available,
            "over_budget": leg.over_budget,
            "price_economy": leg.price_economy_usd,
            "price_business": leg.price_business_usd,
            "price_source": leg.price_source,
            "layover_before": layover_before,
            "booking_url": leg.booking_url or "",
            "contact": leg.contact or "",
            "days": leg.scheduled_days,
            "history": leg_history,
        })

    arrive_label = None
    if route.estimated_arrival:
        dest_tz = 8
        if route.flight_legs:
            dest_tz = AIRPORT_TZ.get(route.flight_legs[-1].destination, 8)
        tz = timezone(timedelta(hours=dest_tz))
        arrive_label = route.estimated_arrival.astimezone(tz).strftime("%a %H:%M") + " " + TZ_LABEL.get(dest_tz, "")

    return {
        "name": route.name,
        "depart_ast": route.depart_ast,
        "arrive_cst": route.arrive_cst,
        "arrive_label": arrive_label,
        "total_hours": round(route.total_hours, 1),
        "wait_hours": round(wait, 1),
        "ground_hours": round(route.ground_hours, 1),
        "flight_hours": round(route.flight_hours, 1),
        "num_stops": route.num_stops,
        "score": round(route.score, 1),
        "reliability": route.reliability.value,
        "risk": route.conflict_proximity.value,
        "price_economy": route.price_economy_usd,
        "price_business": route.price_business_usd,
        "over_budget": any_over_budget,
        "seats_status": seats_status,
        "changed": route.changed,
        "notes": route.notes,
        "booking_urls": route.booking_urls,
        "contacts": route.contacts,
        "legs": legs_data,
        "ground": [
            {"from": s.origin, "to": s.destination, "via": s.via, "hours": s.estimated_hours}
            for s in route.ground_segments
        ],
    }


def start_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
