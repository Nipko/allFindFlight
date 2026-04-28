"""Google Flights adapter via fast-flights (uses internal protobuf endpoint)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.adapters.base import FlightAdapter, SearchError
from app.core.logging import get_logger
from app.models.offer import FlightOffer, FlightSegment, OfferSource

log = get_logger("adapter.google_flights")


class GoogleFlightsAdapter(FlightAdapter):
    source = OfferSource.GOOGLE_FLIGHTS

    def search(
        self,
        origin: str,
        destination: str,
        departure: date,
        return_date: date | None = None,
        adults: int = 1,
    ) -> list[FlightOffer]:
        try:
            # fast-flights: deferred import so the package isn't required at boot
            from fast_flights import FlightData, Passengers, create_filter, get_flights
        except ImportError as e:
            raise SearchError(f"fast-flights not installed: {e}") from e

        flight_data = [
            FlightData(date=departure.isoformat(), from_airport=origin, to_airport=destination)
        ]
        if return_date:
            flight_data.append(
                FlightData(
                    date=return_date.isoformat(),
                    from_airport=destination,
                    to_airport=origin,
                )
            )

        try:
            search_filter = create_filter(
                flight_data=flight_data,
                trip="round-trip" if return_date else "one-way",
                seat="economy",
                passengers=Passengers(adults=adults),
            )
            result = get_flights(search_filter)
        except Exception as e:
            raise SearchError(f"google_flights search failed: {e}") from e

        offers: list[FlightOffer] = []
        for flight in getattr(result, "flights", []) or []:
            offer = self._parse(flight, origin, destination, departure)
            if offer:
                offers.append(offer)

        log.info("gf.search", od=f"{origin}-{destination}", date=departure.isoformat(), count=len(offers))
        return offers

    @staticmethod
    def _parse(flight, origin: str, destination: str, departure: date) -> FlightOffer | None:
        price = _parse_price(getattr(flight, "price", None))
        if price is None:
            return None

        dep_dt = _parse_time(getattr(flight, "departure", None), departure)
        arr_date = departure
        if hasattr(flight, "arrival") and "+" in str(flight.arrival):
            try:
                arr_date = departure + timedelta(days=int(str(flight.arrival).split("+")[-1][0]))
            except (ValueError, IndexError):
                pass
        arr_dt = _parse_time(getattr(flight, "arrival", None), arr_date)

        carrier_name = getattr(flight, "name", "") or "Unknown"
        carrier_code = (carrier_name[:2] or "??").upper()

        segment = FlightSegment(
            carrier=carrier_code,
            flight_number=None,
            origin=origin,
            destination=destination,
            departure=dep_dt or datetime.combine(departure, datetime.min.time()),
            arrival=arr_dt or datetime.combine(arr_date, datetime.min.time()),
            duration_minutes=_parse_duration(getattr(flight, "duration", None)),
        )

        return FlightOffer(
            source=OfferSource.GOOGLE_FLIGHTS,
            segments=[segment],
            price=price,
            currency="USD",
            raw={"name": carrier_name, "stops": getattr(flight, "stops", None)},
        )


def _parse_price(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).replace("$", "").replace(",", "").replace("€", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_time(raw, on_date: date) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip().split(" on ")[0].split("+")[0].strip()
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            t = datetime.strptime(s, fmt).time()
            return datetime.combine(on_date, t)
        except ValueError:
            continue
    return None


def _parse_duration(raw) -> int | None:
    if not raw:
        return None
    s = str(raw).lower()
    hours = minutes = 0
    if "hr" in s or "h " in s:
        try:
            hours = int(s.split("hr")[0].split("h")[0].strip())
        except ValueError:
            pass
    if "min" in s or "m" in s:
        try:
            mpart = s.split("hr")[-1] if "hr" in s else s
            minutes = int("".join(c for c in mpart.split("min")[0] if c.isdigit()) or 0)
        except ValueError:
            pass
    total = hours * 60 + minutes
    return total or None
