from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.aggregator.engine import run_search
from app.core.db import get_session
from app.models.offer import FlightOffer

router = APIRouter(tags=["search"])


class SearchResponse(BaseModel):
    query: dict
    expanded_origins: list[str]
    expanded_destinations: list[str]
    offers: list[FlightOffer]
    sources_used: list[str]
    sources_failed: list[str]


@router.get("/search", response_model=SearchResponse)
def search(
    origin: str = Query(..., description="IATA o ciudad"),
    destination: str = Query(..., description="IATA o ciudad"),
    departure: date = Query(..., description="Fecha de salida YYYY-MM-DD"),
    return_date: date | None = Query(None, alias="return"),
    adults: int = Query(1, ge=1, le=9),
    expand_nearby: bool = Query(True, description="Expandir a aeropuertos cercanos"),
    radius_km: int = Query(200, ge=0, le=500),
    session: Session = Depends(get_session),
) -> SearchResponse:
    return run_search(
        session=session,
        origin=origin,
        destination=destination,
        departure=departure,
        return_date=return_date,
        adults=adults,
        expand_nearby=expand_nearby,
        radius_km=radius_km,
    )
