from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

AST = timezone(timedelta(hours=3))   # Arabia Standard Time
CST = timezone(timedelta(hours=8))   # China Standard Time
TRT = timezone(timedelta(hours=3))   # Turkey Time (same offset as AST)


class FlightStatus(str, Enum):
    OPERATING = "operating"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    DELAYED = "delayed"
    UNKNOWN = "unknown"
    LANDED = "landed"


class AirspaceState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    RESTRICTED = "restricted"


class EscapeRouteType(str, Enum):
    LAND = "land"
    SEA = "sea"
    DOMESTIC_FLIGHT = "domestic_flight"


class ConflictProximity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class ReliabilityScore(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Airport(BaseModel):
    code: str
    name: str
    city: str
    country: str
    status: AirspaceState = AirspaceState.OPEN
    priority: int = 0
    notes: str = ""


class EscapeRoute(BaseModel):
    route_type: EscapeRouteType
    origin: str
    destination: str
    via: str = ""
    estimated_hours: float
    notes: str = ""
    status: str = "unknown"


class FlightLeg(BaseModel):
    flight_number: str
    airline: str
    origin: str
    destination: str
    scheduled_days: list[str] = Field(default_factory=list)
    depart_utc: str = ""
    arrive_utc: str = ""
    duration_hours: float = 0
    aircraft: str = ""
    contact: str = ""
    booking_url: str = ""
    price_economy_usd: Optional[float] = None
    price_business_usd: Optional[float] = None
    seats_available: Optional[bool] = None
    conflict_proximity: ConflictProximity = ConflictProximity.MEDIUM
    status: FlightStatus = FlightStatus.UNKNOWN
    status_source: str = ""
    price_source: str = ""
    over_budget: bool = False
    seats_sufficient: Optional[bool] = None
    last_checked: Optional[datetime] = None


class Route(BaseModel):
    name: str = ""
    ground_segments: list[EscapeRoute] = Field(default_factory=list)
    flight_legs: list[FlightLeg] = Field(default_factory=list)
    total_hours: float = 0
    score: float = 0
    reliability: ReliabilityScore = ReliabilityScore.MEDIUM
    conflict_proximity: ConflictProximity = ConflictProximity.MEDIUM
    notes: str = ""
    next_departure: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    price_economy_usd: Optional[float] = None
    price_business_usd: Optional[float] = None
    layover_hours: list[float] = Field(default_factory=list)
    booking_urls: list[str] = Field(default_factory=list)
    contacts: list[str] = Field(default_factory=list)
    previous_status: Optional[str] = None
    changed: bool = False

    @property
    def num_stops(self) -> int:
        return max(0, len(self.flight_legs) - 1)

    @property
    def ground_hours(self) -> float:
        return sum(s.estimated_hours for s in self.ground_segments)

    @property
    def flight_hours(self) -> float:
        return sum(leg.duration_hours for leg in self.flight_legs)

    @property
    def depart_ast(self) -> Optional[str]:
        if self.next_departure:
            return self.next_departure.astimezone(AST).strftime("%a %b %d, %H:%M AST")
        return None

    @property
    def arrive_cst(self) -> Optional[str]:
        if self.estimated_arrival:
            return self.estimated_arrival.astimezone(CST).strftime("%a %b %d, %H:%M CST")
        return None


class UserProfile(BaseModel):
    passengers: int = 1
    passport: str = "CN"
    budget_usd: float = 10000
    destination_flex: str = "anywhere"
    risk_tolerance: str = "moderate"


class Scenario(BaseModel):
    name: str
    description: str = ""
    origin_city: str
    origin_airport: str
    origin_status: AirspaceState
    destination_country: str
    preferred_destinations: list[Airport] = Field(default_factory=list)
    escape_routes: list[EscapeRoute] = Field(default_factory=list)
    operational_airports: list[Airport] = Field(default_factory=list)
    safe_hubs: list[Airport] = Field(default_factory=list)
    airspace_closed: list[str] = Field(default_factory=list)
    airspace_open: list[str] = Field(default_factory=list)
    airspace_restricted: list[str] = Field(default_factory=list)
    known_flights: list[FlightLeg] = Field(default_factory=list)
    user: UserProfile = Field(default_factory=UserProfile)
