"""Search orchestration: expand OD pairs, run adapters in parallel, dedup, rank."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from sqlalchemy.orm import Session

from app.adapters import ALL_ADAPTERS, get_adapter
from app.core.logging import get_logger
from app.geo.airports import find_by_city_or_iata, nearby_to_airport
from app.models.offer import FlightOffer

log = get_logger("aggregator")

MAX_PARALLEL = 8


def run_search(
    session: Session,
    origin: str,
    destination: str,
    departure: date,
    return_date: date | None,
    adults: int,
    expand_nearby: bool,
    radius_km: int,
) -> dict:
    origin_iatas = _resolve(session, origin, expand_nearby, radius_km)
    dest_iatas = _resolve(session, destination, expand_nearby, radius_km)

    if not origin_iatas or not dest_iatas:
        return {
            "query": _query(origin, destination, departure, return_date, adults),
            "expanded_origins": origin_iatas,
            "expanded_destinations": dest_iatas,
            "offers": [],
            "sources_used": [],
            "sources_failed": [],
        }

    od_pairs = [(o, d) for o in origin_iatas for d in dest_iatas if o != d]
    log.info("search.run", od_pairs=len(od_pairs), adapters=ALL_ADAPTERS)

    offers: list[FlightOffer] = []
    used: set[str] = set()
    failed: set[str] = set()

    jobs = [
        (adapter_name, o, d) for adapter_name in ALL_ADAPTERS for o, d in od_pairs
    ]

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        future_to_job = {
            pool.submit(
                _run_one, adapter_name, o, d, departure, return_date, adults
            ): (adapter_name, o, d)
            for adapter_name, o, d in jobs
        }
        for future in as_completed(future_to_job):
            adapter_name, o, d = future_to_job[future]
            try:
                result = future.result()
                offers.extend(result)
                used.add(adapter_name)
            except Exception as e:
                failed.add(adapter_name)
                log.warning(
                    "search.adapter_failed",
                    adapter=adapter_name,
                    od=f"{o}-{d}",
                    err=str(e),
                )

    deduped = _dedup(offers)
    deduped.sort(key=lambda o: o.price)

    return {
        "query": _query(origin, destination, departure, return_date, adults),
        "expanded_origins": origin_iatas,
        "expanded_destinations": dest_iatas,
        "offers": deduped[:50],
        "sources_used": sorted(used),
        "sources_failed": sorted(failed - used),
    }


def _run_one(
    adapter_name: str,
    origin: str,
    destination: str,
    departure: date,
    return_date: date | None,
    adults: int,
) -> list[FlightOffer]:
    adapter = get_adapter(adapter_name)
    return adapter.search(
        origin=origin,
        destination=destination,
        departure=departure,
        return_date=return_date,
        adults=adults,
    )


def _resolve(session: Session, query: str, expand: bool, radius_km: int) -> list[str]:
    matches = find_by_city_or_iata(session, query)
    if not matches:
        return []
    iatas = {a.iata for a in matches}
    if expand:
        for a in matches:
            for nearby in nearby_to_airport(session, a.iata, radius_km=radius_km):
                iatas.add(nearby.iata)
    return sorted(iatas)


def _dedup(offers: list[FlightOffer]) -> list[FlightOffer]:
    seen: dict[str, FlightOffer] = {}
    for o in offers:
        k = o.dedup_key()
        if k not in seen or o.price < seen[k].price:
            seen[k] = o
    return list(seen.values())


def _query(origin, destination, departure, return_date, adults) -> dict:
    return {
        "origin": origin,
        "destination": destination,
        "departure": departure.isoformat(),
        "return": return_date.isoformat() if return_date else None,
        "adults": adults,
    }
