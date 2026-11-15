"""Offline tests for the NWFF scraper. Run with:  pytest"""
from datetime import date, datetime
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.sources import nwff

FIXTURES = Path(__file__).parent / "fixtures" / "nwff"
TODAY = date(2026, 11, 14)
LS = "https://nwfilmforum.org/films/unstreamable-love-streams/"
GF = "https://nwfilmforum.org/films/go-fish-4k-restoration/"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def week1():
    return nwff.parse_week(load("calendar_2026-11-14.html"))


@pytest.fixture(scope="module")
def details():
    return {LS: nwff.parse_detail(load("film_unstreamable-love-streams.html")),
            GF: nwff.parse_detail(load("film_go-fish-4k-restoration.html"))}


@pytest.fixture(scope="module")
def records(details):
    items = nwff.parse_week(load("calendar_2026-11-14.html"))[0] + nwff.parse_week(load("calendar_2026-11-20.html"))[0]
    return nwff.build_screenings(items, details)


def find(records, title, day):
    match = [r for r in records if r.title == title and r.date == day]
    assert len(match) == 1, f"{title} {day}: {len(match)}"
    return match[0]


def test_week_parsing(week1):
    items, next_start = week1
    assert len(items) == 6
    assert next_start == "2026-11-20"
    assert items[0].start == datetime(2026, 11, 13, 17, 0) and items[0].duration_min == 99
    event = [i for i in items if i.kind == "event"]
    assert len(event) == 1 and event[0].url.endswith("/events/seattle-film-societys-film-discussion-group/")


def test_detail_parsing(details):
    assert details[LS] == {
        "directors": ["John Cassavetes"], "year": 1984, "runtime_min": 140, "series": "Unstreamable",
        "ticket_url": "https://nwfilmforum.eventive.org/films/6a206600823a0bf897418220", "format": None,
    }
    assert details[GF]["series"] is None and details[GF]["runtime_min"] == 88


def test_one_record_checked_in_full(records):
    r = find(records, "Love Streams", "2026-11-21")
    assert r.to_dict() == {
        "id": "nwff|2026-11-21|love-streams",
        "venue_id": "nwff",
        "date": "2026-11-21",
        "title": "Love Streams",
        "showtimes": [
            {"time": "16:00", "ticket_url": "https://nwfilmforum.eventive.org/films/6a206600823a0bf897418220", "note": None, "sold_out": False},
            {"time": "19:00", "ticket_url": "https://nwfilmforum.eventive.org/films/6a206600823a0bf897418220", "note": None, "sold_out": False},
        ],
        "kind": "film",
        "series": "Unstreamable",
        "directors": ["John Cassavetes"],
        "year": 1984,
        "runtime_min": 140,
        "format": None,
        "notes": [],
        "url": LS,
    }


def test_restoration_moves_to_a_note(records):
    r = find(records, "Go Fish", "2026-11-17")
    assert r.notes == ["4K restoration"] and r.directors == ["Rose Troche"] and r.year == 1994


def test_events_kept_with_kind_event(records):
    r = find(records, "Seattle Film Society's Film Discussion Group", "2026-11-18")
    assert r.kind == "event" and r.runtime_min is None


def test_attribute_icons_become_notes(records):
    r = find(records, "Seattle Film Society Presents Locals Only: November 2026", "2026-11-19")
    assert r.notes == ["Visiting artist"]


def test_on_film_sets_format_and_workshops_are_skipped():
    html = load("calendar_2026-11-14.html")
    on_film = html.replace('<div class="calendar-popup__attributes">\n</div>',
                           '<div class="calendar-popup__attributes"><i class="attribute-icon icon-on_film"></i></div>')
    workshop = on_film.replace("calendar__item--event", "calendar__item--workshop")
    items, _ = nwff.parse_week(workshop)
    assert all(i.kind == "film" for i in items)  # the workshop is gone
    records = nwff.build_screenings(items, {})
    # Every item whose attribute box was empty now says "On Film" (Locals Only had its own icon).
    assert {r.format for r in records if "Locals Only" not in r.title} == {"Film"}


def test_title_without_series_line_keeps_its_prefix():
    title, notes = nwff.clean_title("Unstreamable - Love Streams", None)
    assert title == "Unstreamable - Love Streams" and notes == []


def test_every_record_is_valid(records):
    for r in records:
        r.validate({"nwff"})


class FakeHttp:
    request_count = 0

    def __init__(self):
        self.urls = []

    def get_text(self, url, **kwargs):
        self.urls.append(url)
        if "start=2026-11-14" in url:
            return load("calendar_2026-11-14.html")
        if "start=2026-11-20" in url:
            return load("calendar_2026-11-20.html")
        if "start=" in url:
            return "<div class='calendar__day-list'></div>"
        if url == LS:
            return load("film_unstreamable-love-streams.html")
        return load("film_go-fish-4k-restoration.html")


def test_fetch_follows_next_week_links_and_drops_past_days():
    http = FakeHttp()
    records = nwff.fetch(Context(http=http, today=TODAY, horizon_days=21))
    weeks = [u for u in http.urls if "calendar" in u]
    assert weeks == ["https://nwfilmforum.org/calendar/?start=2026-11-14",
                     "https://nwfilmforum.org/calendar/?start=2026-11-20",
                     "https://nwfilmforum.org/calendar/?start=2026-11-27"]
    assert min(r.date for r in records) == "2026-11-15"  # the Nov 13 showing is in the past
