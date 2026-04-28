from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OfferSource(str, Enum):
    GOOGLE_FLIGHTS = "google_flights"
    RYANAIR = "ryanair"
    WIZZAIR = "wizzair"
    AMADEUS = "amadeus"
    KIWI = "kiwi"


class FlightSegment(BaseModel):
    carrier: str
    flight_number: str | None = None
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    duration_minutes: int | None = None


class FlightOffer(BaseModel):
    """Common normalized model for any flight result."""

    source: OfferSource
    segments: list[FlightSegment]
    price: float
    currency: str = "EUR"
    price_with_carry_on: float | None = None
    price_with_checked_bag: float | None = None
    booking_url: str | None = None
    raw: dict | None = Field(default=None, exclude=True, repr=False)

    @property
    def origin(self) -> str:
        return self.segments[0].origin

    @property
    def destination(self) -> str:
        return self.segments[-1].destination

    @property
    def departure(self) -> datetime:
        return self.segments[0].departure

    @property
    def arrival(self) -> datetime:
        return self.segments[-1].arrival

    @property
    def stops(self) -> int:
        return max(0, len(self.segments) - 1)

    @property
    def carriers(self) -> list[str]:
        return list(dict.fromkeys(s.carrier for s in self.segments))

    def dedup_key(self) -> str:
        """Identity for deduplication across sources."""
        first = self.segments[0]
        last = self.segments[-1]
        return (
            f"{first.carrier}{first.flight_number or ''}|"
            f"{first.departure.isoformat()}|"
            f"{last.arrival.isoformat()}|"
            f"{last.destination}"
        )
