"""Offline tests for the Beacon scraper. Run with:  pytest"""
from datetime import date
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.sources import beacon

FIXTURES = Path(__file__).parent / "fixtures" / "beacon"
TODAY = date(2026, 11, 14)
MARTHA = "https://thebeacon.film/calendar/movie/the-strange-love-of-martha-ivers"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def entries():
    return beacon.parse_calendar(load("calendar.html"), TODAY)


@pytest.fixture(scope="module")
def records(entries):
    details = {MARTHA: beacon.parse_detail(load(f"movie_the-strange-love-of-martha-ivers.html"))}
    return beacon.build_screenings(entries, details)


def find(records, title, day):
    match = [r for r in records if r.title == title and r.date == day]
    assert len(match) == 1, f"{title} {day}: {len(match)}"
    return match[0]


def test_rentals_are_skipped_and_everything_else_kept(entries):
    # The fixture has 11 film showtimes and 6 "Rent the Beacon" slots.
    assert len(entries) == 11
    assert not any("rent" in e.title.lower() for e in entries)


def test_one_record_checked_in_full(records):
    r = find(records, "The Strange Love of Martha Ivers", "2026-11-15")
    assert r.to_dict() == {
        "id": "beacon|2026-11-15|the-strange-love-of-martha-ivers",
        "venue_id": "beacon",
        "date": "2026-11-15",
        "title": "The Strange Love of Martha Ivers",
        "showtimes": [{
            "time": "14:00",
            "ticket_url": MARTHA + "?showtime=25THBWWJ3JBGSLHT2WBYKMUX",
            "note": None,
            "sold_out": False,
        }],
        "kind": "film",
        "series": None,
        "directors": ["Lewis Milestone"],
        "year": 1946,
        "runtime_min": 116,
        "format": None,
        "notes": [],
        "url": MARTHA,
    }


def test_year_rolls_over_into_january(entries):
    january = sorted({e.date for e in entries if e.date.startswith("2027")})
    assert january == ["2027-01-20", "2027-01-30"]


def test_two_showtimes_same_day_become_one_record_sold_out_kept(records):
    r = find(records, "Fire Walk Without Me", "2027-01-20")
    assert [(s.time, s.sold_out, s.ticket_url) for s in r.showtimes] == [("19:30", True, None), ("21:30", True, None)]


def test_title_case_and_free_note(records):
    titles = {r.title for r in records}
    assert {"Will Success Spoil Rock Hunter?", "Buffalo '66", "Once Upon a Time in Harlem", "Nationtime"} <= titles
    free = find(records, "Junior Boys – The Gore", "2027-01-30")
    assert free.notes == ["Free admission"] and free.showtimes[0].ticket_url is None


def test_every_record_is_valid(records):
    for r in records:
        r.validate({"beacon"})
        assert r.title == r.title.strip() and not r.title.isupper()


def test_weekday_decides_the_year():
    assert beacon.resolve_date("Saturday, January 2", TODAY) == date(2027, 1, 2)
    assert beacon.resolve_date("Thursday, November 12", TODAY) == date(2026, 11, 12)
    with pytest.raises(beacon.ParseError):
        beacon.resolve_date("Tuesday, November 15", TODAY)  # Nov 15 is Sat, Sun, Mon in 2025-2027


def test_changed_layout_is_an_error():
    with pytest.raises(beacon.ParseError):
        beacon.parse_calendar("<html><body><p>New design</p></body></html>", TODAY)


def test_detail_falls_back_to_visible_runtime():
    html = "<main><p>Director Someone</p><p>Runtime 1h 32m</p></main>"
    assert beacon.parse_detail(html) == {"directors": [], "year": None, "runtime_min": 92}


class FakeHttp:
    request_count = 0

    def __init__(self):
        self.urls = []

    def get_text(self, url, **kwargs):
        self.urls.append(url)
        if url == beacon.CALENDAR_URL:
            return load("calendar.html")
        return load("movie_the-strange-love-of-martha-ivers.html")


def test_fetch_uses_the_cache_and_respects_the_horizon():
    http = FakeHttp()
    ctx = Context(http=http, today=TODAY, horizon_days=10)
    records = beacon.fetch(ctx)
    assert max(r.date for r in records) == "2026-11-24"  # January is past the horizon
    films = {u for u in http.urls if u != beacon.CALENDAR_URL}
    assert len(films) == 6  # one detail request per film
    http.urls.clear()
    beacon.fetch(ctx)  # second run: details come from the cache
    assert http.urls == [beacon.CALENDAR_URL]
