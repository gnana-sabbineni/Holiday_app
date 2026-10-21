from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(String(2))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    primary_type: Mapped[str] = mapped_column(String(80), index=True)
    types: Mapped[list[str]] = mapped_column(JSON, default=list)
    nationwide: Mapped[bool] = mapped_column(Boolean, default=False)
    locations: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(300))
    urlid: Mapped[str | None] = mapped_column(String(120))

    # like .Include(h => h.States): loaded together with the holiday
    state_rows: Mapped[list["HolidayState"]] = relationship(
        back_populates="holiday", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def states(self) -> list[str]:
        return sorted(s.abbrev for s in self.state_rows)


class HolidayState(Base):
    __tablename__ = "holiday_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    holiday_id: Mapped[int] = mapped_column(ForeignKey("holidays.id"), index=True)
    abbrev: Mapped[str] = mapped_column(String(2), index=True)
    note: Mapped[str | None] = mapped_column(String(40))  # "partly" / "optional" / None

    holiday: Mapped[Holiday] = relationship(back_populates="state_rows")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))