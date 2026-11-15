"""Offline tests for the Majestic Bay scraper. Run with:  pytest"""
import json
from datetime import date
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.sources import majestic_bay as mb

FIXTURES = Path(__file__).parent / "fixtures" / "majestic_bay"
TODAY = date(2026, 11, 14)


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def records():
    return mb.build_screenings(mb.parse_schedule(json.loads(load("schedule.json"))),
                               mb.parse_movies(json.loads(load("movies.json"))))


def find(records, title, day):
    match = [r for r in records if r.title == title and r.date == day]
    assert len(match) == 1, f"{title} {day}: {len(match)}"
    return match[0]


def test_counts(records):
    # 9 films; 15 film-days in the trimmed fixture (3 films on one day, 6 on two).
    assert len(records) == 15
    assert len({r.title for r in records}) == 9


def test_one_record_checked_in_full(records):
    r = find(records, "Wildwood", "2026-11-15")
    assert r.to_dict() == {
        "id": "majestic-bay|2026-11-15|wildwood",
        "venue_id": "majestic-bay",
        "date": "2026-11-15",
        "title": "Wildwood",
        "showtimes": [
            {"time": "12:00", "ticket_url": "https://ticketing.us.veezi.com/purchase/36800?siteToken=Z6qUv91cr0aCDg%2bCM%2bZ7zQ%3d%3d", "note": None, "sold_out": False},
            {"time": "15:15", "ticket_url": "https://ticketing.us.veezi.com/purchase/36804?siteToken=Z6qUv91cr0aCDg%2bCM%2bZ7zQ%3d%3d", "note": None, "sold_out": False},
            {"time": "18:45", "ticket_url": "https://ticketing.us.veezi.com/purchase/36806?siteToken=Z6qUv91cr0aCDg%2bCM%2bZ7zQ%3d%3d", "note": None, "sold_out": False},
        ],
        "kind": "film",
        "series": None,
        "directors": ["Travis Knight"],
        "year": 2026,
        "runtime_min": 131,
        "format": "Digital",
        "notes": [],
        "url": "https://www.majesticbay.com/",
    }


def test_missing_release_date_leaves_year_empty(records):
    r = find(records, "Star Trek IV: The Voyage Home", "2026-11-25")
    assert r.year is None and r.runtime_min == 119 and r.directors == ["Leonard Nimoy"]


def test_unknown_projection_tag_gives_no_format():
    schedule = json.loads(load("schedule.json"))
    schedule["X05TV"]["schedule"]["4854"]["2026-12-02"][0]["tags"] = ["Format.Projection.Laser"]
    records = mb.build_screenings(mb.parse_schedule(schedule), mb.parse_movies(json.loads(load("movies.json"))))
    assert find(records, "Star Trek: First Contact", "2026-12-02").format is None


def test_every_record_is_valid(records):
    for r in records:
        r.validate({"majestic-bay"})


def test_changed_api_is_an_error():
    with pytest.raises(mb.ParseError):
        mb.parse_schedule({"error": "nope"})
    with pytest.raises(mb.ParseError):
        mb.build_screenings(mb.parse_schedule(json.loads(load("schedule.json"))), {})


class FakeHttp:
    request_count = 0

    def __init__(self):
        self.urls = []

    def get_text(self, url, **kwargs):
        self.urls.append(url)
        return load("schedule.json") if "schedule?" in url else load("movies.json")


def test_fetch_is_two_requests_and_trims_to_the_horizon():
    http = FakeHttp()
    records = mb.fetch(Context(http=http, today=TODAY, horizon_days=7))
    assert len(http.urls) == 2
    assert "from=2026-11-14T03:00:00&to=2026-11-22T03:00:00" in http.urls[0]
    assert "%22X05TV%22" in http.urls[0]
    assert max(r.date for r in records) == "2026-11-20"
    assert "ids=1000004528" in http.urls[1] and "ids=4854" not in http.urls[1]  # Dec 2 film not asked for
