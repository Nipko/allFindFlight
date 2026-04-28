"""Airport lookup and nearby search using H3."""

from __future__ import annotations

import h3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.airport import Airport

# H3 resolution 4 -> avg edge ~22 km, hex area ~1770 km^2.
# k=3 -> ~150-200 km radius, suitable for nearby-airport expansion.
H3_RESOLUTION = 4

# Airport types from OurAirports we care about for commercial flights.
COMMERCIAL_TYPES = {"large_airport", "medium_airport"}


def airport_h3(lat: float, lng: float, resolution: int = H3_RESOLUTION) -> str:
    return h3.latlng_to_cell(lat, lng, resolution)


def find_by_iata(session: Session, iata: str) -> Airport | None:
    return session.get(Airport, iata.upper())


def find_by_city_or_iata(session: Session, query: str) -> list[Airport]:
    """Resolve a free-text query to one or more airports.

    If `query` is a 3-letter IATA code, return that airport.
    Otherwise match by municipality (case-insensitive, prefix).
    """
    q = query.strip()
    if len(q) == 3 and q.isalpha():
        airport = find_by_iata(session, q)
        if airport:
            return [airport]

    stmt = (
        select(Airport)
        .where(Airport.municipality.ilike(f"{q}%"))
        .where(Airport.type.in_(COMMERCIAL_TYPES))
        .order_by(Airport.type.desc())
        .limit(10)
    )
    return list(session.scalars(stmt).all())


def nearby_airports(
    session: Session,
    lat: float,
    lng: float,
    radius_km: int = 200,
    types: set[str] | None = None,
) -> list[Airport]:
    """Find commercial airports within ~radius_km using H3 ring expansion.

    H3 ring is geodesic-only (no real travel time). For now this is good enough
    for pre-filtering; refine with Google Distance Matrix later.
    """
    types = types or COMMERCIAL_TYPES

    # k = ceil(radius_km / ~45km per ring at res 4)
    k = max(1, round(radius_km / 45))

    center = h3.latlng_to_cell(lat, lng, H3_RESOLUTION)
    ring_cells = h3.grid_disk(center, k)

    stmt = (
        select(Airport)
        .where(Airport.h3_index.in_(list(ring_cells)))
        .where(Airport.type.in_(types))
    )
    candidates = list(session.scalars(stmt).all())

    # Final filter by actual geodesic distance (H3 disk over-approximates).
    radius_deg_sq = (radius_km / 111.0) ** 2
    return [
        a
        for a in candidates
        if (a.latitude - lat) ** 2 + (a.longitude - lng) ** 2 <= radius_deg_sq * 1.5
    ]


def nearby_to_airport(
    session: Session,
    iata: str,
    radius_km: int = 200,
    include_self: bool = True,
) -> list[Airport]:
    """Nearby airports to a given IATA code (used to expand origin/destination)."""
    base = find_by_iata(session, iata)
    if not base:
        return []
    results = nearby_airports(session, base.latitude, base.longitude, radius_km)
    if not include_self:
        results = [a for a in results if a.iata != base.iata]
    elif not any(a.iata == base.iata for a in results):
        results.append(base)
    return results
