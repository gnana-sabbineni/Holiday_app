from sqlalchemy import func, select

from app.ingest import replace_holidays
from app.models import Holiday, HolidayState, HolidayStateLink

from .common_methods import holidays_sample_data


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_each_state_is_stored_once(db_session):
    replace_holidays(db_session, holidays_sample_data())

    nv_rows = db_session.scalars(
        select(HolidayState).where(HolidayState.country_code == "US", HolidayState.abbrev == "NV")
    ).all()
    assert len(nv_rows) == 1                                   # ONE row for NV...
    assert len(nv_rows[0].holiday_links) == 2                  # ...linked to both NV holidays


def test_same_abbrev_in_two_countries_are_separate_states(db_session):
    replace_holidays(db_session, holidays_sample_data())

    wa = db_session.scalars(select(HolidayState).where(HolidayState.abbrev == "WA")).all()
    assert sorted(s.country_code for s in wa) == ["AU", "US"]


def test_reingest_does_not_duplicate_anything(db_session):
    replace_holidays(db_session, holidays_sample_data())
    before = (_count(db_session, Holiday), _count(db_session, HolidayState), _count(db_session, HolidayStateLink))

    replace_holidays(db_session, holidays_sample_data())
    after = (_count(db_session, Holiday), _count(db_session, HolidayState), _count(db_session, HolidayStateLink))

    assert before == after == (5, 4, 5)  # 5 holidays, states NV/TX/US-WA/AU-WA, 5 links


def test_holiday_states_property_lists_abbrevs(db_session):
    replace_holidays(db_session, holidays_sample_data())

    juneteenth = db_session.scalar(select(Holiday).where(Holiday.name == "Juneteenth Day"))
    assert juneteenth.states == ["NV", "TX"]


def test_state_filter_includes_nationwide_and_linked_holidays(client, auth_headers, db_session):
    replace_holidays(db_session, holidays_sample_data())

    response = client.get("/holidays", params={"state": "NV", "country": "US"}, headers=auth_headers)

    names = {h["name"] for h in response.json()["items"]}
    assert names == {"Juneteenth Day", "Nevada Day", "Independence Day"}  # 2 linked + 1 nationwide


def test_country_filter_separates_equal_abbreviations(client, auth_headers, db_session):
    replace_holidays(db_session, holidays_sample_data())

    response = client.get("/holidays", params={"state": "WA", "country": "AU"}, headers=auth_headers)

    assert [h["name"] for h in response.json()["items"]] == ["Western Australia Day"]
