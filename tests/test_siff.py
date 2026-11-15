"""Offline tests for the SIFF scraper. Run with:  pytest"""
from datetime import date
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.models import Screening, Showtime, ValidationError
from scrapers.sources import siff

FIXTURES = Path(__file__).parent / "fixtures" / "siff"
DAY = date(2026, 11, 17)


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def items():
    return siff.parse_day(load("calendar_2026-11-17.html"), DAY)


@pytest.fixture(scope="module")
def records(items):
    return siff.build_screenings(items)


def by_title(records, title):
    matches = [record for record in records if record.title == title]
    assert len(matches) == 1, f"expected one {title!r}, got {len(matches)}"
    return matches[0]


# --- parsing -----------------------------------------------------------------


def test_counts_match_what_the_live_page_showed(items):
    # Counted independently in the browser on 2026-11-14: 6 films, 9 showtimes.
    assert len(items) == 6
    shows = [show for item in items for show in item.shows]
    assert len(shows) == 9
    per_venue = {venue: sum(s.venue_id == venue for s in shows) for venue in siff.VENUE_IDS}
    assert per_venue == {"siff-uptown": 6, "siff-downtown": 2, "siff-film-center": 1}


def test_venue_comes_from_the_link_not_the_auditorium_name(items):
    # The embedded data says "SIFF Cinema Uptown House 2"; we want "siff-uptown".
    first = items[0]
    assert {show.venue_id for show in first.shows} == {"siff-uptown"}


def test_empty_day_returns_nothing():
    assert siff.parse_day(load("calendar_2027-03-02_empty.html"), date(2027, 3, 2)) == []


def test_wrong_date_is_an_error():
    with pytest.raises(siff.ParseError):
        siff.parse_day(load("calendar_2026-11-17.html"), date(2026, 11, 18))


def test_changed_layout_is_an_error_not_an_empty_result():
    with pytest.raises(siff.ParseError):
        siff.parse_day("<html><body><p>Something else entirely</p></body></html>", DAY)
    broken = load("calendar_2026-11-17.html").replace("data-screening=", "data-other=")
    with pytest.raises(siff.ParseError):
        siff.parse_day(broken, DAY)


# --- cleaning ----------------------------------------------------------------


def test_one_record_checked_in_full(records):
    record = by_title(records, "Paper Tiger")
    assert record.to_dict() == {
        "id": "siff-uptown|2026-11-17|paper-tiger",
        "venue_id": "siff-uptown",
        "date": "2026-11-17",
        "title": "Paper Tiger",
        "showtimes": [
            {"time": "16:00", "ticket_url": None, "note": None, "sold_out": False},
            {"time": "19:00", "ticket_url": None, "note": None, "sold_out": False},
        ],
        "kind": "film",
        "series": None,
        "directors": ["James Gray"],
        "year": 2026,
        "runtime_min": 114,
        "format": "35mm",
        "notes": [],
        "url": "https://www.siff.net/cinema/in-theaters/paper-tiger-(35mm)",
    }


def test_series_prefix_is_split_off(records):
    record = by_title(records, "My Night at Maud’s")
    assert record.series == "Nouvelles Femmes"
    assert record.directors == ["Éric Rohmer"]
    assert record.year == 1969
    assert record.notes == ["SIFF year-round passes are not valid for this series."]
    assert record.id == "siff-uptown|2026-11-17|my-night-at-mauds"


def test_two_directors_and_plain_titles(records):
    record = by_title(records, "You Can See Everything")
    assert record.directors == ["Nathan Fielder", "Lance Oppenheim"]
    assert record.series is None and record.format is None
    assert [show.time for show in record.showtimes] == ["15:45", "19:15"]


def test_every_record_is_valid_and_clean(records):
    assert len(records) == 6
    for record in records:
        record.validate(set(siff.VENUE_IDS))
        assert "mm)" not in record.title and ": " not in record.title


@pytest.mark.parametrize(
    "meta, expected",
    [
        ("USA | 2026 | 175 min. | Nathan Fielder, Lance Oppenheim", (2026, 175, ["Nathan Fielder", "Lance Oppenheim"])),
        ("USA | 1958 | 145 | Morton DaCosta", (1958, 145, ["Morton DaCosta"])),  # no "min."
        ("Romania | 2026 | 85 min.", (2026, 85, [])),  # no director
        ("USA | 2026 | 105 min.  | John M. Keller", (2026, 105, ["John M. Keller"])),  # double space
        ("", (None, None, [])),
    ],
)
def test_parse_meta(meta, expected):
    assert siff.parse_meta(meta) == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Paper Tiger (35mm)", ("Paper Tiger", "35mm")),
        ("Paper Tiger [35mm]", ("Paper Tiger", "35mm")),
        ("Lawrence of Arabia (70MM)", ("Lawrence of Arabia", "70mm")),
        ("The Heart of the Game (20th anniversary)", ("The Heart of the Game (20th anniversary)", None)),
    ],
)
def test_split_format(title, expected):
    assert siff.split_format(title) == expected


def test_split_series_rules():
    # Confirmed by the ticketing name.
    assert siff.split_series("Community Screening: Auntie Mame", "Auntie Mame", set()) == (
        "Auntie Mame",
        "Community Screening",
    )
    # A colon that is part of the title stays.
    assert siff.split_series("Mission: Impossible", "Mission: Impossible", set()) == ("Mission: Impossible", None)
    # Same prefix on several titles in the run.
    assert siff.split_series("Cinema Italian Style 2026: Gioia", "", {"Cinema Italian Style 2026"}) == (
        "Gioia",
        "Cinema Italian Style 2026",
    )
    # Known list.
    assert siff.split_series("The Open Road: Route One/USA", "", set()) == ("Route One/USA", "The Open Road")


# --- fetch (with a fake network) ----------------------------------------------


class FakeHttp:
    def __init__(self, pages):
        self.pages, self.urls, self.request_count = pages, [], 0

    def get_text(self, url):
        self.urls.append(url)
        self.request_count += 1
        day = url.rsplit("date=", 1)[1]
        d = date.fromisoformat(day)
        heading = f"{d:%A, %B} {d.day}, {d.year}"  # no %-d: it fails on Windows
        empty = f'<div class="h1"><span>{heading}</span></div>'
        return self.pages.get(day, empty)


def test_fetch_walks_days_and_stops_after_a_run_of_empty_ones():
    http = FakeHttp({"2026-11-17": load("calendar_2026-11-17.html")})
    ctx = Context(http=http, today=date(2026, 11, 16), horizon_days=21)
    records = siff.fetch(ctx)
    assert len(records) == 6
    # Nov 16 (empty), Nov 17 (full), then 5 empty days: 7 requests, not 22.
    assert len(http.urls) == 7
    assert http.urls[0] == "https://www.siff.net/calendar?view=list&date=2026-11-16"


# --- model ---------------------------------------------------------------------


def test_validation_rejects_bad_records():
    good = dict(venue_id="siff-uptown", date="2026-11-17", title="X", showtimes=[Showtime("19:00")])
    Screening(**good).validate({"siff-uptown"})
    for change in (
        {"venue_id": "nowhere"},
        {"date": "11/17/2026"},
        {"title": " X "},
        {"format": "IMAX"},
        {"showtimes": []},
        {"showtimes": [Showtime("7:00 PM")]},
        {"showtimes": [Showtime("19:00"), Showtime("16:00")]},
        {"notes": ["x" * 201]},
    ):
        with pytest.raises(ValidationError):
            Screening(**{**good, **change}).validate({"siff-uptown"})
