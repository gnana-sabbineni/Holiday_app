from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Every country gets ONE extra row in holiday_states that stands for "the whole country".
# Nationwide holidays link to it, so every holiday can find its country through its states.
NATIONWIDE_ABBREV = "ALL"
NATIONWIDE_NAME = "Nationwide"


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))                    # "United States"
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)  # "US"


class HolidayState(Base):
    """ONE row per state/province/region of a country, e.g. (United States, NV).

    The same abbreviation can exist in several countries (US "WA" = Washington,
    AU "WA" = Western Australia), so a state is identified by country + abbrev.
    The row with is_nationwide=True means "the whole country".
    """

    __tablename__ = "holiday_states"
    __table_args__ = (
        UniqueConstraint("country_id", "abbrev", name="uq_holiday_states_country_abbrev"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), index=True)
    abbrev: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str | None] = mapped_column(String(100))   # "Nevada"
    iso: Mapped[str | None] = mapped_column(String(20))     # "us-nv"
    is_nationwide: Mapped[bool] = mapped_column(Boolean, default=False)

    # joined: the country is fetched in the same query as the state (no extra query)
    country: Mapped[Country] = relationship(lazy="joined")
    holiday_links: Mapped[list["HolidayStateLink"]] = relationship(
        back_populates="state", cascade="all, delete-orphan"
    )


class Holiday(Base):
    """A holiday. It has NO country column: its country is found through its states
    (holiday -> holiday_state_links -> holiday_states -> countries)."""

    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    primary_type: Mapped[str] = mapped_column(String(80), index=True)
    types: Mapped[list[str]] = mapped_column(JSON, default=list)
    nationwide: Mapped[bool] = mapped_column(Boolean, default=False)
    locations: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(300))
    urlid: Mapped[str | None] = mapped_column(String(120))

    # The assignments "this holiday applies to these states". Deleting a holiday
    # deletes its links (never the states themselves - those are shared).
    state_links: Mapped[list["HolidayStateLink"]] = relationship(
        back_populates="holiday", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def states(self) -> list[str]:
        """Abbreviations of the listed states ([] for a nationwide holiday)."""
        return sorted(
            link.state.abbrev for link in self.state_links if not link.state.is_nationwide
        )

    @property
    def country_code(self) -> str | None:
        """Country, found through the first linked state."""
        for link in self.state_links:
            return link.state.country.code
        return None


class HolidayStateLink(Base):
    """Which holiday applies to which state (many-to-many).

    The primary key is (holiday_id, state_id), so the database itself refuses to
    link the same state to the same holiday twice.
    """

    __tablename__ = "holiday_state_links"

    holiday_id: Mapped[int] = mapped_column(
        ForeignKey("holidays.id", ondelete="CASCADE"), primary_key=True
    )
    state_id: Mapped[int] = mapped_column(
        ForeignKey("holiday_states.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    note: Mapped[str | None] = mapped_column(String(100))  # "partly" / "optional" / None

    holiday: Mapped[Holiday] = relationship(back_populates="state_links")
    # joined: the state row is fetched in the same query as the link (no extra query per link)
    state: Mapped[HolidayState] = relationship(back_populates="holiday_links", lazy="joined")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
