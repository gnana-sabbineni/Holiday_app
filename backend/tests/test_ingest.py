import pytest
from sqlalchemy import func, select

from app.ingest import load_country
from app.models import Country, Holiday, HolidayState, HolidayStateLink

from .common_methods import au_records, load_sample_data, us_records


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _counts(db):
    return tuple(_count(db, m) for m in (Holiday, Country, HolidayState, HolidayStateLink))


def _holiday(db, name):
    return db.scalar(select(Holiday).where(Holiday.name == name))


def test_each_state_is_stored_once_and_linked_to_every_holiday(db_session):
    load_sample_data(db_session)

    nv = db_session.scalars(select(HolidayState).where(HolidayState.abbrev == "NV")).all()
    assert len(nv) == 1                                  # ONE row for NV...
    assert len(nv[0].holiday_links) == 2                 # ...linked to both NV holidays
    assert nv[0].country.code == "US"


def test_same_abbrev_in_two_countries_are_separate_states(db_session):
    load_sample_data(db_session)

    wa = db_session.scalars(select(HolidayState).where(HolidayState.abbrev == "WA")).all()
    assert sorted(s.country.code for s in wa) == ["AU", "US"]
    assert len({s.country_id for s in wa}) == 2


def test_country_row_is_created_from_the_file_and_reused(db_session):
    result = load_country(db_session, us_records())
    assert result.country_created is True

    again = load_country(db_session, us_records())
    assert again.country_created is False
    countries = db_session.scalars(select(Country)).all()
    assert [(c.code, c.name) for c in countries] == [("US", "United States")]


def test_reingest_does_not_duplicate_anything(db_session):
    load_sample_data(db_session)
    before = _counts(db_session)
    load_sample_data(db_session)

    assert _counts(db_session) == before
    # 6 holidays, 2 countries, 6 states (NV, TX, US-WA, AU-WA + two "ALL" rows), 7 links
    assert before == (6, 2, 6, 7)


def test_nationwide_holiday_links_to_the_country_wide_row(db_session):
    load_sample_data(db_session)

    holiday = _holiday(db_session, "Independence Day")
    assert holiday.nationwide is True
    assert holiday.states == []                           # no listed states...
    assert holiday.country_code == "US"                   # ...but the country is still known
    assert [link.state.is_nationwide for link in holiday.state_links] == [True]


def test_holiday_country_and_states_come_through_the_states(db_session):
    load_sample_data(db_session)

    assert _holiday(db_session, "Juneteenth Day").states == ["NV", "TX"]
    assert _holiday(db_session, "Juneteenth Day").country_code == "US"
    assert _holiday(db_session, "Western Australia Day").country_code == "AU"


def test_reingest_replaces_only_that_countrys_holidays(db_session):
    load_sample_data(db_session)

    load_country(db_session, us_records()[:1])            # reload the US with just ONE holiday

    names = set(db_session.scalars(select(Holiday.name)))
    assert names == {"Juneteenth Day", "Western Australia Day", "Australia Day"}   # AU untouched


def test_new_state_details_are_filled_in_on_a_later_ingest(db_session):
    load_country(db_session, us_records())                # sample states have no names
    records = us_records()
    records[1]["states"][0].update(name="Nevada", iso="us-nv")

    load_country(db_session, records)

    nv = db_session.scalar(select(HolidayState).where(HolidayState.abbrev == "NV"))
    assert (nv.name, nv.iso) == ("Nevada", "us-nv")


def test_file_without_country_needs_the_override(db_session):
    records = us_records()
    for r in records:
        r["country_code"] = r["country_name"] = None

    with pytest.raises(ValueError, match="--country"):
        load_country(db_session, records)

    result = load_country(db_session, records, country_code="us")
    assert result.country_code == "US"
    assert db_session.scalar(select(Country.name).where(Country.code == "US")) == "US"  # placeholder name


def test_override_that_disagrees_with_the_file_is_rejected(db_session):
    with pytest.raises(ValueError, match="does not match"):
        load_country(db_session, us_records(), country_code="IN")
    assert _counts(db_session) == (0, 0, 0, 0)            # nothing saved


def test_file_with_two_countries_is_rejected(db_session):
    with pytest.raises(ValueError, match="mixes several countries"):
        load_country(db_session, us_records() + au_records())
    assert _counts(db_session) == (0, 0, 0, 0)


def test_holiday_with_no_states_that_is_not_nationwide_is_rejected(db_session):
    records = us_records()
    records[0]["states"] = []                             # not nationwide, and no state either

    with pytest.raises(ValueError, match="no country"):
        load_country(db_session, records)
    assert _counts(db_session) == (0, 0, 0, 0)


def test_dry_run_checks_everything_but_saves_nothing(db_session):
    result = load_country(db_session, us_records(), dry_run=True)

    assert result.holidays == 4 and result.states_used == 3 and result.country_created is True
    assert _counts(db_session) == (0, 0, 0, 0)
