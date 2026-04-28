"""Download OurAirports CSV and load into Postgres with H3 index.

Run: python -m app.scripts.seed_airports
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx

from app.core.db import Base, SessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.geo.airports import airport_h3
from app.models.airport import Airport

OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
LOCAL_PATH = Path(__file__).resolve().parents[2] / ".." / "data" / "airports.csv"

ALLOWED_TYPES = {"large_airport", "medium_airport", "small_airport"}

log = get_logger("seed_airports")


def fetch_csv() -> str:
    if LOCAL_PATH.exists():
        log.info("seed.using_local", path=str(LOCAL_PATH))
        return LOCAL_PATH.read_text(encoding="utf-8")
    log.info("seed.downloading", url=OURAIRPORTS_URL)
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        r = client.get(OURAIRPORTS_URL)
        r.raise_for_status()
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_PATH.write_text(r.text, encoding="utf-8")
    return r.text


def parse_rows(content: str):
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        iata = (row.get("iata_code") or "").strip().upper()
        if not iata or len(iata) != 3:
            continue
        if row.get("type") not in ALLOWED_TYPES:
            continue
        try:
            lat = float(row["latitude_deg"])
            lng = float(row["longitude_deg"])
        except (KeyError, ValueError):
            continue
        elev = row.get("elevation_ft") or ""
        try:
            elevation_ft = int(elev) if elev else None
        except ValueError:
            elevation_ft = None
        yield Airport(
            iata=iata,
            icao=(row.get("ident") or None),
            name=row.get("name") or "",
            municipality=row.get("municipality") or None,
            iso_country=row.get("iso_country") or None,
            iso_region=row.get("iso_region") or None,
            type=row.get("type"),
            latitude=lat,
            longitude=lng,
            elevation_ft=elevation_ft,
            h3_index=airport_h3(lat, lng),
        )


def run() -> None:
    configure_logging()
    Base.metadata.create_all(engine)

    content = fetch_csv()
    airports = list(parse_rows(content))
    log.info("seed.parsed", count=len(airports))

    with SessionLocal() as session:
        session.query(Airport).delete()
        session.bulk_save_objects(airports)
        session.commit()

    log.info("seed.done", count=len(airports))


if __name__ == "__main__":
    run()
