"""Ryanair direct adapter using the public farfnd endpoint.

Ryanair exposes an unauthenticated JSON endpoint that returns the cheapest fare
per day in a date range. We use it for cheapest-fare discovery and a separate
endpoint (`/booking/v4/...`) for the actual roundtrip availability.

Note: this hits Ryanair directly. Use rate limiting and (eventually) proxies.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from curl_cffi import requests as cffi_requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.adapters.base import FlightAdapter, SearchError
from app.core.logging import get_logger
from app.models.offer import FlightOffer, FlightSegment, OfferSource

log = get_logger("adapter.ryanair")

CHEAPEST_PER_DAY_URL = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
ROUNDTRIP_AVAIL_URL = "https://www.ryanair.com/api/booking/v4/en-gb/availability"

# Real browser headers + impersonation make Ryanair accept us.
_BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Origin": "https://www.ryanair.com",
    "Referer": "https://www.ryanair.com/",
}


class RyanairAdapter(FlightAdapter):
    source = OfferSource.RYANAIR

    def __init__(self, currency: str = "EUR") -> None:
        self.currency = currency

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _get_json(self, url: str, params: dict) -> dict:
        resp = cffi_requests.get(
            url,
            params=params,
            headers=_BROWSER_HEADERS,
            impersonate="chrome120",
            timeout=20,
        )
        if resp.status_code != 200:
            raise SearchError(f"ryanair {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def search(
        self,
        origin: str,
        destination: str,
        departure: date,
        return_date: date | None = None,
        adults: int = 1,
    ) -> list[FlightOffer]:
        params = {
            "departureAirportIataCode": origin,
            "arrivalAirportIataCode": destination,
            "language": "en",
            "limit": 50,
            "market": "en-gb",
            "offset": 0,
            "outboundDepartureDateFrom": departure.isoformat(),
            "outboundDepartureDateTo": (departure + timedelta(days=1)).isoformat(),
        }
        if return_date:
            params["inboundDepartureDateFrom"] = return_date.isoformat()
            params["inboundDepartureDateTo"] = (return_date + timedelta(days=1)).isoformat()

        try:
            data = self._get_json(CHEAPEST_PER_DAY_URL, params)
        except Exception as e:
            raise SearchError(f"ryanair fetch failed: {e}") from e

        offers: list[FlightOffer] = []
        for fare in data.get("fares", []):
            offer = self._parse_fare(fare, origin, destination, return_date is not None)
            if offer:
                offers.append(offer)

        log.info(
            "ryanair.search",
            od=f"{origin}-{destination}",
            date=departure.isoformat(),
            count=len(offers),
        )
        return offers

    @staticmethod
    def _parse_fare(fare: dict, origin: str, destination: str, has_return: bool) -> FlightOffer | None:
        outbound = fare.get("outbound") or {}
        price_obj = outbound.get("price") or {}
        price = price_obj.get("value")
        if price is None:
            return None

        dep_str = outbound.get("departureDate")
        arr_str = outbound.get("arrivalDate")
        if not dep_str or not arr_str:
            return None

        dep = _parse_iso(dep_str)
        arr = _parse_iso(arr_str)
        flight_no = (outbound.get("flightNumber") or "").replace(" ", "")

        segments = [
            FlightSegment(
                carrier="FR",
                flight_number=flight_no,
                origin=origin,
                destination=destination,
                departure=dep,
                arrival=arr,
                duration_minutes=int((arr - dep).total_seconds() // 60),
            )
        ]

        if has_return:
            inbound = fare.get("inbound") or {}
            ib_dep = _parse_iso(inbound.get("departureDate")) if inbound.get("departureDate") else None
            ib_arr = _parse_iso(inbound.get("arrivalDate")) if inbound.get("arrivalDate") else None
            ib_no = (inbound.get("flightNumber") or "").replace(" ", "")
            ib_price = (inbound.get("price") or {}).get("value")
            if ib_dep and ib_arr:
                segments.append(
                    FlightSegment(
                        carrier="FR",
                        flight_number=ib_no,
                        origin=destination,
                        destination=origin,
                        departure=ib_dep,
                        arrival=ib_arr,
                        duration_minutes=int((ib_arr - ib_dep).total_seconds() // 60),
                    )
                )
                if ib_price:
                    price = price + ib_price

        return FlightOffer(
            source=OfferSource.RYANAIR,
            segments=segments,
            price=float(price),
            currency=price_obj.get("currencyCode", "EUR"),
            booking_url=(
                f"https://www.ryanair.com/gb/en/trip/flights/select"
                f"?adults=1&dateOut={segments[0].departure.date().isoformat()}"
                f"&originIata={origin}&destinationIata={destination}"
            ),
            raw={"fare": fare},
        )


def _parse_iso(s: str) -> datetime:
    # Ryanair returns "2026-06-15T07:30:00.000" or with offset; use fromisoformat after trim.
    return datetime.fromisoformat(s.replace("Z", "+00:00").split(".")[0])
