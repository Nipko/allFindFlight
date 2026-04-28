from app.adapters.base import FlightAdapter, SearchError
from app.adapters.google_flights import GoogleFlightsAdapter
from app.adapters.ryanair import RyanairAdapter

_REGISTRY: dict[str, type[FlightAdapter]] = {
    "google_flights": GoogleFlightsAdapter,
    "ryanair": RyanairAdapter,
}

ALL_ADAPTERS = list(_REGISTRY.keys())


def get_adapter(name: str) -> FlightAdapter:
    cls = _REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown adapter: {name}")
    return cls()


__all__ = ["FlightAdapter", "SearchError", "get_adapter", "ALL_ADAPTERS"]
