from __future__ import annotations

from pathlib import Path

import yaml

from .models import (
    Airport,
    AirspaceState,
    ConflictProximity,
    EscapeRoute,
    EscapeRouteType,
    FlightLeg,
    Scenario,
    UserProfile,
)


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    origin = raw["origin"]
    dest = raw["destination"]
    scenario_meta = raw["scenario"]

    user_raw = raw.get("user", {})
    user = UserProfile(
        passengers=user_raw.get("passengers", 1),
        passport=user_raw.get("passport", "CN"),
        budget_usd=user_raw.get("budget_usd", 10000),
        destination_flex=user_raw.get("destination_flex", "anywhere"),
        risk_tolerance=user_raw.get("risk_tolerance", "moderate"),
    )

    preferred = [
        Airport(code=c["code"], name=c["name"], city=c.get("name", ""), country=dest["country"])
        for c in dest.get("preferred_cities", [])
    ]

    escape = [
        EscapeRoute(
            route_type=EscapeRouteType(r["type"]),
            origin=r["from"],
            destination=r["to"],
            via=r.get("via", ""),
            estimated_hours=r["estimated_hours"],
            notes=r.get("notes", ""),
            status=r.get("status", "unknown"),
        )
        for r in raw.get("escape_routes", [])
    ]

    airports = [
        Airport(
            code=a["code"],
            name=a["name"],
            city=a["city"],
            country=a["country"],
            status=AirspaceState(a.get("status", "open")),
            priority=a.get("priority", 0),
            notes=a.get("notes", ""),
        )
        for a in raw.get("operational_airports", [])
    ]

    hubs = [
        Airport(
            code=h["code"],
            name=h["name"],
            city=h["city"],
            country=h["country"],
            notes=h.get("notes", ""),
        )
        for h in raw.get("safe_hubs", [])
    ]

    proximity_map = {
        "low": ConflictProximity.LOW,
        "medium": ConflictProximity.MEDIUM,
        "high": ConflictProximity.HIGH,
        "blocked": ConflictProximity.BLOCKED,
    }

    flights = [
        FlightLeg(
            flight_number=fl["flight_number"],
            airline=fl["airline"],
            origin=fl["origin"],
            destination=fl["destination"],
            scheduled_days=fl.get("days", []),
            depart_utc=fl.get("depart_utc", ""),
            arrive_utc=fl.get("arrive_utc", ""),
            duration_hours=fl.get("duration_hours", 0),
            aircraft=fl.get("aircraft", ""),
            contact=fl.get("contact", ""),
            booking_url=fl.get("booking_url", ""),
            price_economy_usd=fl.get("price_economy_usd"),
            price_business_usd=fl.get("price_business_usd"),
            conflict_proximity=proximity_map.get(
                fl.get("conflict_proximity", "medium"), ConflictProximity.MEDIUM
            ),
        )
        for fl in raw.get("known_flights", [])
    ]

    airspace = raw.get("airspace_status", {})

    return Scenario(
        name=scenario_meta["name"],
        description=scenario_meta.get("description", ""),
        conflict_start=scenario_meta.get("conflict_start", "2026-02-28"),
        origin_city=origin["city"],
        origin_airport=origin["airport_code"],
        origin_status=AirspaceState(origin.get("airport_status", "closed")),
        destination_country=dest["country"],
        preferred_destinations=preferred,
        escape_routes=escape,
        operational_airports=airports,
        safe_hubs=hubs,
        airspace_closed=airspace.get("closed", []),
        airspace_open=airspace.get("open", []),
        airspace_restricted=airspace.get("restricted", []),
        known_flights=flights,
        user=user,
    )
