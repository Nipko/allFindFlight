from datetime import date

from app.adapters import get_adapter
from app.core.logging import get_logger
from app.workers.celery_app import celery_app

log = get_logger("workers")


@celery_app.task(name="search_one_route", bind=True, max_retries=2)
def search_one_route(
    self,
    adapter_name: str,
    origin: str,
    destination: str,
    departure: str,
    return_date: str | None = None,
    adults: int = 1,
) -> list[dict]:
    """Run a single search on a single adapter for a single OD pair."""
    adapter = get_adapter(adapter_name)
    try:
        offers = adapter.search(
            origin=origin,
            destination=destination,
            departure=date.fromisoformat(departure),
            return_date=date.fromisoformat(return_date) if return_date else None,
            adults=adults,
        )
        return [o.model_dump(mode="json") for o in offers]
    except Exception as e:
        log.warning("search.failed", adapter=adapter_name, od=f"{origin}-{destination}", err=str(e))
        raise self.retry(exc=e, countdown=2) from e
