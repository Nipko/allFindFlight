from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.models.offer import FlightOffer, OfferSource


class SearchError(Exception):
    pass


class FlightAdapter(ABC):
    """Uniform interface every flight source must implement."""

    source: OfferSource

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        departure: date,
        return_date: date | None = None,
        adults: int = 1,
    ) -> list[FlightOffer]:
        """Return normalized offers. Raise SearchError on hard failure."""
