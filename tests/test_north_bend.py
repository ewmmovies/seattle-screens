"""Offline tests for the North Bend scraper. Run with:  pytest"""
from datetime import date
from pathlib import Path

import pytest

from scrapers.context import Context
from scrapers.sources import north_bend as nb

FIXTURES = Path(__file__).parent / "fixtures" / "north_bend"
TODAY = date(2026, 11, 15)
BASE = "https://tix.northbendtheatre.com/event/"
MINIVER = BASE + "mrs-miniver-sunday-nov-15th-3pm"
HUNGER_3PM = BASE + "the-hunger-games-sunrise-on-the-reaping-saturday-nov-28th-7pm"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def listings():
    return nb.parse_index(load("index.html"))


def event(day, time, year=None, runtime=None):
    return {"date": day, "time": time, "year": year, "runtime_min": runtime}


def test_index_dedupes_and_keeps_every_category(listings):
    assert len(listings) == 8  # 10 links, two events listed twice
    alien = next(l for l in listings if l.title.startswith("Alien Private Eye"))
    assert alien.categories == ["Analog Anomalies", "Free Shows!"]


def test_event_page_date_line_wins_over_the_web_address():
    parsed = nb.parse_event(load("event_the-hunger-games-sunrise-on-the-reaping-saturday-nov-28th-7pm.html"))
    assert (parsed["date"], parsed["time"]) == ("2026-11-28", "15:00")  # address says 7pm


def test_one_record_checked_in_full(listings):
    events = {MINIVER: nb.parse_event(load("event_mrs-miniver-sunday-nov-15th-3pm.html"))}
    [record] = nb.build_screenings(listings, events)
    assert record.to_dict() == {
        "id": "north-bend|2026-11-15|mrs-miniver",
        "venue_id": "north-bend",
        "date": "2026-11-15",
        "title": "Mrs. Miniver",
        "showtimes": [{"time": "15:00", "ticket_url": MINIVER, "note": None, "sold_out": False}],
        "kind": "film",
        "series": "Love & War",
        "directors": [],
        "year": 1942,
        "runtime_min": 134,
        "format": None,
        "notes": [],
        "url": MINIVER,
    }


def test_series_free_note_and_own_title_category(listings):
    events = {l.url: event("2026-11-18", "19:00") for l in listings}
    records = {r.title: r for r in nb.build_screenings(listings, events)}
    alien = records["Alien Private Eye"]
    assert alien.series == "Analog Anomalies" and alien.notes == ["Free admission"]
    assert records["Godzilla Minus Zero"].series is None  # its category is just its own title
    assert records["Warren Miller’s Days Off"].series == "Mountain Film Festival"
    assert "Teton Gravity Research presents: Actually, It Is Rocket Science The 31st Annual TGR Ski Film" in records


def test_same_title_same_day_merges_into_one_record(listings):
    events = {l.url: event("2026-11-28", "15:00" if l.url == HUNGER_3PM else "19:00")
              for l in listings if "hunger-games" in l.url and "nov-28th" in l.url}
    [record] = nb.build_screenings(listings, events)
    assert [s.time for s in record.showtimes] == ["15:00", "19:00"]


def test_comedy_is_a_live_event():
    html = load("index.html").replace("Analog Anomalies", "Live Comedy")
    listings = nb.parse_index(html)
    records = nb.build_screenings(listings, {l.url: event("2026-11-18", "19:00") for l in listings})
    alien = next(r for r in records if r.title == "Alien Private Eye")
    assert alien.kind == "event" and alien.series == "Live Comedy"


def test_title_cleaning():
    assert nb.clean_title("Mrs. Miniver (Sunday Nov. 15th @3pm)") == "Mrs. Miniver"
    assert nb.clean_title("The Way Out- Matchstick Productions (Sunday November 29th @3pm)") == "The Way Out- Matchstick Productions"
    assert nb.clean_title("Rear Window (1954)") == "Rear Window (1954)"  # not a day/time: left alone


def test_layout_change_is_an_error():
    with pytest.raises(nb.ParseError):
        nb.parse_index("<html><body>New site</body></html>")
    with pytest.raises(nb.ParseError):
        nb.parse_event("<html><body><h3 class='date'>Coming soon</h3></body></html>")


class FakeHttp:
    request_count = 0

    def __init__(self):
        self.urls = []

    def get_text(self, url, **kwargs):
        self.urls.append(url)
        if url == nb.INDEX_URL:
            return load("index.html")
        if url == HUNGER_3PM:
            return load("event_the-hunger-games-sunrise-on-the-reaping-saturday-nov-28th-7pm.html")
        return load("event_mrs-miniver-sunday-nov-15th-3pm.html")


def test_fetch_reads_each_event_once_and_uses_the_cache():
    http = FakeHttp()
    ctx = Context(http=http, today=TODAY, horizon_days=21)
    records = nb.fetch(ctx)
    assert len(http.urls) == 9  # index + 8 events
    for r in records:
        r.validate({"north-bend"})
    http.urls.clear()
    nb.fetch(ctx)
    assert http.urls == [nb.INDEX_URL]
