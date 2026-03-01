"""Route planner: builds complete escape routes and ranks them by balanced score."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import (
    AST,
    CST,
    Airport,
    ConflictProximity,
    EscapeRoute,
    FlightLeg,
    FlightStatus,
    ReliabilityScore,
    Route,
    Scenario,
)
from .searcher import next_departure_date

RELIABILITY_ORDER = {
    ReliabilityScore.HIGH: 0,
    ReliabilityScore.MEDIUM: 1,
    ReliabilityScore.LOW: 2,
}

STATUS_TO_RELIABILITY = {
    FlightStatus.OPERATING: ReliabilityScore.HIGH,
    FlightStatus.LANDED: ReliabilityScore.HIGH,
    FlightStatus.SCHEDULED: ReliabilityScore.MEDIUM,
    FlightStatus.UNKNOWN: ReliabilityScore.MEDIUM,
    FlightStatus.DELAYED: ReliabilityScore.MEDIUM,
    FlightStatus.CANCELLED: ReliabilityScore.LOW,
}

PROXIMITY_PENALTY = {
    ConflictProximity.LOW: 0,
    ConflictProximity.MEDIUM: 2,
    ConflictProximity.HIGH: 10,
    ConflictProximity.BLOCKED: 999,
}

PROXIMITY_ORDER = {
    ConflictProximity.LOW: 0,
    ConflictProximity.MEDIUM: 1,
    ConflictProximity.HIGH: 2,
    ConflictProximity.BLOCKED: 3,
}


def build_routes(
    scenario: Scenario,
    now: Optional[datetime] = None,
    previous_routes: Optional[list[Route]] = None,
    speed_mode: str = "balanced",
    max_stops: int = 2,
    max_wait_hours: float = 72,
) -> list[Route]:
    if now is None:
        now = datetime.now(timezone.utc)

    prev_map: dict[str, Route] = {}
    if previous_routes:
        for r in previous_routes:
            prev_map[r.name] = r

    routes: list[Route] = []
    ground_to_airport = _build_ground_segments(scenario)
    reachable_airports = {a.code for a in scenario.operational_airports}
    dest_codes = {d.code for d in scenario.preferred_destinations}
    hub_codes = {h.code for h in scenario.safe_hubs}

    for flight in scenario.known_flights:
        departs_from_reachable = flight.origin in reachable_airports

        if flight.status == FlightStatus.CANCELLED and departs_from_reachable:
            cancelled_route = _build_single_flight_route(
                flight, ground_to_airport, scenario, now
            )
            if cancelled_route:
                cancelled_route.reliability = ReliabilityScore.LOW
                cancelled_route.notes = "CANCELLED — check for rebooking"
                routes.append(cancelled_route)
            continue

        if departs_from_reachable and flight.destination in dest_codes:
            route = _build_single_flight_route(flight, ground_to_airport, scenario, now)
            if route:
                routes.append(route)

        elif departs_from_reachable and flight.destination in hub_codes:
            connecting = _build_connection_routes(
                flight, ground_to_airport, scenario, now
            )
            routes.extend(connecting)

    # Filter by max stops
    routes = [r for r in routes if r.num_stops <= max_stops]

    # Filter by max wait
    routes = [
        r for r in routes
        if r.next_departure is None
        or (r.next_departure - now).total_seconds() / 3600 <= max_wait_hours
        or r.reliability == ReliabilityScore.LOW  # keep cancelled for visibility
    ]

    routes = _score_and_sort(routes, now, scenario, speed_mode)

    # Tag changes from previous run
    for route in routes:
        prev = prev_map.get(route.name)
        if prev:
            old_statuses = "|".join(l.status.value for l in prev.flight_legs)
            new_statuses = "|".join(l.status.value for l in route.flight_legs)
            route.previous_status = old_statuses
            route.changed = old_statuses != new_statuses

    return routes


def _build_ground_segments(scenario: Scenario) -> dict[str, list[EscapeRoute]]:
    result: dict[str, list[EscapeRoute]] = {}
    for airport in scenario.operational_airports:
        segments = _find_ground_path(scenario, airport.city)
        result[airport.code] = segments
    return result


def _find_ground_path(scenario: Scenario, target_city: str) -> list[EscapeRoute]:
    """Find the fastest chain of ground/domestic segments from origin to target.
    When multiple options exist for the same leg (e.g., drive vs fly), pick the fastest."""
    segments: list[EscapeRoute] = []
    visited = {scenario.origin_city}
    current = scenario.origin_city

    for _ in range(10):
        if current.lower() == target_city.lower():
            break

        candidates = [
            r for r in scenario.escape_routes
            if r.origin.lower() == current.lower()
            and r.destination.lower() not in {v.lower() for v in visited}
        ]

        if not candidates:
            break

        # Group by destination, pick fastest for each, then take the one
        # that moves us toward the target
        by_dest: dict[str, list[EscapeRoute]] = {}
        for c in candidates:
            by_dest.setdefault(c.destination.lower(), []).append(c)

        best = None
        for dest_key, options in by_dest.items():
            fastest = min(options, key=lambda r: r.estimated_hours)
            if best is None or fastest.estimated_hours < best.estimated_hours:
                best = fastest

        if best is None:
            break

        segments.append(best)
        visited.add(best.destination)
        current = best.destination

    return segments


def _build_single_flight_route(
    flight: FlightLeg,
    ground_map: dict[str, list[EscapeRoute]],
    scenario: Scenario,
    now: datetime,
) -> Optional[Route]:
    ground = ground_map.get(flight.origin, [])
    next_dep = next_departure_date(flight, after=now)

    reliability = STATUS_TO_RELIABILITY.get(flight.status, ReliabilityScore.MEDIUM)

    dest_name = flight.destination
    for d in scenario.preferred_destinations:
        if d.code == flight.destination:
            dest_name = d.name
            break

    estimated_arrival = None
    if next_dep:
        estimated_arrival = next_dep + timedelta(hours=flight.duration_hours)

    booking_urls = [flight.booking_url] if flight.booking_url else []
    contacts = [flight.contact] if flight.contact else []

    origin_name = flight.origin
    for a in scenario.operational_airports:
        if a.code == flight.origin:
            origin_name = a.city
            break

    nonstop_label = "nonstop" if not ground else f"from {origin_name}"

    return Route(
        name=f"{flight.flight_number} {flight.origin}→{dest_name} ({nonstop_label})",
        ground_segments=list(ground),
        flight_legs=[flight],
        reliability=reliability,
        conflict_proximity=flight.conflict_proximity,
        next_departure=next_dep,
        estimated_arrival=estimated_arrival,
        price_economy_usd=flight.price_economy_usd,
        price_business_usd=flight.price_business_usd,
        booking_urls=booking_urls,
        contacts=contacts,
    )


def _build_connection_routes(
    hub_flight: FlightLeg,
    ground_map: dict[str, list[EscapeRoute]],
    scenario: Scenario,
    now: datetime,
) -> list[Route]:
    routes: list[Route] = []
    ground = ground_map.get(hub_flight.origin, [])

    onward_flights = [
        f for f in scenario.known_flights
        if f.origin == hub_flight.destination
        and f.destination in {d.code for d in scenario.preferred_destinations}
    ]

    for onward in onward_flights:
        hub_dep = next_departure_date(hub_flight, after=now)
        if hub_dep is None:
            continue

        earliest_connect = hub_dep + timedelta(hours=hub_flight.duration_hours + 2)
        onward_dep = next_departure_date(onward, after=earliest_connect)

        dest_name = onward.destination
        for d in scenario.preferred_destinations:
            if d.code == onward.destination:
                dest_name = d.name
                break

        hub_name = hub_flight.destination
        for h in scenario.safe_hubs:
            if h.code == hub_flight.destination:
                hub_name = h.city
                break

        worst_status = _worst_status(hub_flight.status, onward.status)
        reliability = STATUS_TO_RELIABILITY.get(worst_status, ReliabilityScore.MEDIUM)
        worst_proximity = _worst_proximity(hub_flight.conflict_proximity, onward.conflict_proximity)

        layover_hours = 0.0
        if hub_dep and onward_dep:
            layover_hours = (onward_dep - hub_dep).total_seconds() / 3600 - hub_flight.duration_hours

        estimated_arrival = None
        if onward_dep:
            estimated_arrival = onward_dep + timedelta(hours=onward.duration_hours)

        total_economy = None
        total_business = None
        if hub_flight.price_economy_usd and onward.price_economy_usd:
            total_economy = hub_flight.price_economy_usd + onward.price_economy_usd
        if hub_flight.price_business_usd and onward.price_business_usd:
            total_business = hub_flight.price_business_usd + onward.price_business_usd

        booking_urls = []
        contacts = []
        for leg in [hub_flight, onward]:
            if leg.booking_url and leg.booking_url not in booking_urls:
                booking_urls.append(leg.booking_url)
            if leg.contact and leg.contact not in contacts:
                contacts.append(leg.contact)

        origin_name = hub_flight.origin
        for a in scenario.operational_airports:
            if a.code == hub_flight.origin:
                origin_name = a.city
                break

        route = Route(
            name=f"{hub_flight.flight_number}+{onward.flight_number} {origin_name}→{hub_name}→{dest_name}",
            ground_segments=list(ground),
            flight_legs=[hub_flight, onward],
            reliability=reliability,
            conflict_proximity=worst_proximity,
            next_departure=hub_dep,
            estimated_arrival=estimated_arrival,
            price_economy_usd=total_economy,
            price_business_usd=total_business,
            booking_urls=booking_urls,
            contacts=contacts,
            notes=f"Layover in {hub_name}: ~{layover_hours:.1f}h" if layover_hours > 0 else "",
        )
        routes.append(route)

    return routes


def _worst_status(a: FlightStatus, b: FlightStatus) -> FlightStatus:
    priority = {
        FlightStatus.CANCELLED: 0, FlightStatus.UNKNOWN: 1,
        FlightStatus.DELAYED: 2, FlightStatus.SCHEDULED: 3,
        FlightStatus.OPERATING: 4, FlightStatus.LANDED: 5,
    }
    return a if priority.get(a, 1) < priority.get(b, 1) else b


def _worst_proximity(a: ConflictProximity, b: ConflictProximity) -> ConflictProximity:
    return a if PROXIMITY_ORDER.get(a, 1) > PROXIMITY_ORDER.get(b, 1) else b


def _score_and_sort(
    routes: list[Route], now: datetime, scenario: Scenario, speed_mode: str = "balanced",
) -> list[Route]:
    """
    Score routes. Lower = better.
    Modes:
      soonest:        heavily penalizes wait, doesn't care about layovers
      shortest_total: all hours weighed equally
      balanced:       wait * 1.5 + ground + flight + layover * 0.8  (default)
    """
    budget = scenario.user.budget_usd

    for route in routes:
        if route.next_departure:
            wait = max(0, (route.next_departure - now).total_seconds() / 3600)
        else:
            wait = 72

        ground = route.ground_hours
        flight = route.flight_hours
        layover = 2.0 * route.num_stops
        conflict = sum(PROXIMITY_PENALTY.get(l.conflict_proximity, 2) for l in route.flight_legs)

        if speed_mode == "soonest":
            route.score = (wait * 3.0) + ground + flight + (layover * 0.3) + conflict
        elif speed_mode == "shortest_total":
            route.score = wait + ground + flight + layover + conflict
        else:  # balanced
            route.score = (wait * 1.5) + ground + flight + (layover * 0.8) + conflict

        route.total_hours = wait + ground + flight + layover

        if route.price_economy_usd and route.price_economy_usd > budget:
            route.score += 50

    cancelled = [r for r in routes if r.reliability == ReliabilityScore.LOW]
    viable = [r for r in routes if r.reliability != ReliabilityScore.LOW]

    viable.sort(key=lambda r: (RELIABILITY_ORDER.get(r.reliability, 1), r.score))
    cancelled.sort(key=lambda r: r.score)

    return viable + cancelled
