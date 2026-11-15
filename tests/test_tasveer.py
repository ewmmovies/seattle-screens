"""Offline tests for the Tasveer scraper. Run with:  pytest"""
import json
from datetime import date
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.sources import tasveer

FIXTURES = Path(__file__).parent / "fixtures" / "tasveer"
TODAY = date(2026, 11, 15)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records():
    return tasveer.build_screenings(tasveer.parse_showings(load("showings_2026-11-16.json")))


def find(records, title):
    match = [r for r in records if r.title == title]
    assert len(match) == 1, f"{title}: {len(match)}"
    return match[0]


def test_counts_and_merge(records):
    # 6 showings of 4 films; two films show twice.
    assert len(records) == 4
    assert [s.time for s in find(records, "Wild Horse Nine").showtimes] == ["16:15", "19:45"]


def test_utc_times_become_pacific_dates(records):
    assert {r.date for r in records} == {"2026-11-16"}  # all are 2026-11-17 in UTC


def test_one_record_checked_in_full(records):
    r = find(records, "La Bola Negra")
    assert r.to_dict() == {
        "id": "tasveer|2026-11-16|la-bola-negra",
        "venue_id": "tasveer",
        "date": "2026-11-16",
        "title": "La Bola Negra",
        "showtimes": [{"time": "16:30", "ticket_url": None, "note": "English subtitles", "sold_out": False}],
        "kind": "film",
        "series": None,
        "directors": ["Javier Calvo", "Javier Ambrossi"],
        "year": 2026,
        "runtime_min": 155,
        "format": None,
        "notes": [],
        "url": "https://filmcenter.tasveer.org/movie/la-bola-negra-2026-spain-spanish/",
    }


def test_accessibility_badges_are_not_notes(records):
    r = find(records, "Once Upon a Time in Harlem")
    assert all(s.note is None for s in r.showtimes)


def test_title_cleaning():
    assert tasveer.clean_title("You Can See Everything (2026, USA)") == ("You Can See Everything", [])
    assert tasveer.clean_title("Lagaan (2001, India, Hindi) with post-film Q&A") == ("Lagaan", ["With post-film Q&A"])
    assert tasveer.clean_title("Kal Ho Naa Ho (with post-film discussion)") == ("Kal Ho Naa Ho", ["With post-film discussion"])
    assert tasveer.clean_title("Mr. & Mrs. 55") == ("Mr. & Mrs. 55", [])


def test_open_captions_badge_and_unpublished_showings():
    data = load("showings_2026-11-16.json")
    showings = data["data"]["showingsForDate"]["data"]
    showings[0]["displayMetaData"] = json.dumps({"classes": "open-captions wheelchair-accessible"})
    showings[2]["published"] = False
    showings[4]["private"] = True
    records = tasveer.build_screenings(tasveer.parse_showings(data))
    assert find(records, "Wild Horse Nine").showtimes[0].note == "Open captions"
    assert "Once Upon a Time in Harlem" not in {r.title for r in records}


def test_graphql_errors_are_failures():
    denied = {"errors": [{"message": "You do not have permission to perform this action. (Code: 102)"}], "data": None}
    with pytest.raises(tasveer.ParseError, match="permission"):
        tasveer.parse_showings(denied)
    assert tasveer.parse_dates(load("dates.json")) == ["2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]


def test_every_record_is_valid(records):
    for r in records:
        r.validate({"tasveer"})


class FakeHttp:
    request_count = 0

    def __init__(self):
        self.calls = []

    def post_text(self, url, data=None, headers=None, **kwargs):
        body = json.loads(data)
        self.calls.append((url, body["variables"], headers))
        if "datesWithShowing" in body["query"]:
            return json.dumps(load("dates.json"))
        if body["variables"]["date"] == "2026-11-16":
            return json.dumps(load("showings_2026-11-16.json"))
        return json.dumps({"data": {"showingsForDate": {"data": []}}})


def test_fetch_sends_site_headers_and_asks_each_date():
    http = FakeHttp()
    records = tasveer.fetch(Context(http=http, today=TODAY, horizon_days=21))
    assert len(http.calls) == 6  # dates + 5 days
    assert all(h["site-id"] == "262" and h["client-type"] == "consumer" for _, _, h in http.calls)
    assert len(records) == 4
