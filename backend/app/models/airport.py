from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Airport(Base):
    __tablename__ = "airports"

    iata: Mapped[str] = mapped_column(String(3), primary_key=True)
    icao: Mapped[str | None] = mapped_column(String(4))
    name: Mapped[str] = mapped_column(String(255))
    municipality: Mapped[str | None] = mapped_column(String(255))
    iso_country: Mapped[str | None] = mapped_column(String(2), index=True)
    iso_region: Mapped[str | None] = mapped_column(String(10))
    type: Mapped[str | None] = mapped_column(String(32), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    elevation_ft: Mapped[int | None] = mapped_column(Integer)
    h3_index: Mapped[str | None] = mapped_column(String(20), index=True)

    __table_args__ = (
        Index("ix_airports_country_type", "iso_country", "type"),
    )

    def __repr__(self) -> str:
        return f"<Airport {self.iata} {self.municipality}>"
