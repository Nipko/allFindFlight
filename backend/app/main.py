from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import search
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.startup")
    yield
    log.info("app.shutdown")


app = FastAPI(
    title="AllfindFlight",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
