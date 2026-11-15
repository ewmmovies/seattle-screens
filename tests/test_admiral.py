"""Offline tests for the Admiral scraper. Run with:  pytest"""
import json
from datetime import date
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.sources import admiral

FIXTURES = Path(__file__).parent / "fixtures" / "admiral"
TODAY = date(2026, 11, 15)


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed():
    return admiral.parse_day(json.loads(load("showtimes_20261115.json")))


@pytest.fixture(scope="module")
def records(parsed):
    return admiral.build_screenings(parsed[0])


def find(records, title):
    match = [r for r in records if r.title == title]
    assert len(match) == 1, f"{title}: {len(match)}"
    return match[0]


def test_counts_match_the_live_page(records):
    # The page showed 5 films and 12 showtimes on 2026-11-15; Ebenezer had none.
    assert len(records) == 5
    assert sum(len(r.showtimes) for r in records) == 12


def test_times_are_local_wall_clock(records):
    # The live page listed Jimmy at 12:15 PM and 6:30 PM.
    assert [s.time for s in find(records, "Jimmy").showtimes] == ["12:15", "18:30"]
    assert [s.time for s in find(records, "You Can See Everything").showtimes] == ["12:00", "14:50", "18:05"]


def test_one_record_checked_in_full(records):
    r = find(records, "The Cat in the Hat")
    site = "https://www.farawayentertainment.com/"
    assert r.to_dict() == {
        "id": "admiral|2026-11-15|the-cat-in-the-hat",
        "venue_id": "admiral",
        "date": "2026-11-15",
        "title": "The Cat in the Hat",
        "showtimes": [
            {"time": "12:40", "ticket_url": site, "note": "Open captions", "sold_out": False},
            {"time": "15:20", "ticket_url": site, "note": None, "sold_out": False},
            {"time": "18:30", "ticket_url": site, "note": None, "sold_out": False},
        ],
        "kind": "film",
        "series": None,
        "directors": ["Erica Rivinoja", "Alessandro Carloni"],
        "year": 2026,
        "runtime_min": 114,
        "format": None,
        "notes": [],
        "url": site,
    }


def test_valid_dates(parsed):
    _, dates = parsed
    assert dates[:3] == ["2026-11-15", "2026-11-16", "2026-11-17"] and "2026-11-28" not in dates


def test_eid_is_read_from_the_home_page():
    assert admiral.find_eid(load("home.html")) == "efbc509c-5e9b-4178-8dc6-a2e635ba8057"
    assert admiral.find_eid("<html>no key</html>") is None


def test_api_error_is_a_failure():
    with pytest.raises(admiral.ParseError):
        admiral.parse_day({"error": True, "error_message": "bad eid"})


def test_every_record_is_valid(records):
    for r in records:
        r.validate({"admiral"})


class FakeHttp:
    request_count = 0

    def __init__(self):
        self.bodies = []

    def get_text(self, url, **kwargs):
        return load("home.html")

    def post_text(self, url, data=None, **kwargs):
        self.bodies.append(json.loads(data))
        assert "headers" not in kwargs  # sent as plain text, like the site
        if self.bodies[-1]["date"] == "20261115":
            return load("showtimes_20261115.json")
        return json.dumps({"error": False, "validDates": {}, "films": []})


def test_fetch_asks_each_valid_date_in_the_horizon():
    http = FakeHttp()
    records = admiral.fetch(Context(http=http, today=TODAY, horizon_days=21))
    asked = [b["date"] for b in http.bodies]
    assert asked[0] == "20261115" and "20261205" in asked and "20261128" not in asked
    assert all(b["location"] == "00001-00001-00002" for b in http.bodies)
    assert len(records) == 5
