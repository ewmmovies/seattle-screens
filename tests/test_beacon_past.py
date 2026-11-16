"""Past Programs page: the Beacon's past programs and past series (added 2026-11-15)."""
from datetime import date
from pathlib import Path

import requests

from scrapers import build, run
from scrapers.context import Context
from scrapers.posts import beacon, beacon_past

FIXTURES = Path(__file__).parent / "fixtures" / "posts"
TODAY = date(2026, 11, 15)


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class Http:
    """Serves the fixtures; every past page gets the past-program fixture, Double Features its own."""

    def __init__(self, fail=()):
        self.pages, self.fail = [], set(fail)

    def get_text(self, url, **kwargs):
        if url == beacon.PROGRAMS_URL:
            return load("beacon_programs.html")
        if url == beacon.SERIES_URL:
            return load("beacon_series.html")
        self.pages.append(url)
        if url in self.fail:
            raise requests.HTTPError(f"500 for {url}")
        if url.endswith("/series/double-features"):
            return load("beacon_series_double-features.html")
        return load("beacon_program_in-the-midst.html")


def test_past_programs_and_series_are_read():
    posts = beacon_past.fetch(Context(http=Http(), today=TODAY, cache={}))
    programs = [p for p in posts if p.category == "Program"]
    series = [p for p in posts if p.category == "Series"]
    assert len(programs) == 4 and programs[0].date_label == "May 2026" and programs[0].published == "2026-05-01"
    assert [s.title for s in series] == ["Double Features"] and series[0].published is None  # never seen playing
    assert series[0].description == "Trust us, you've got to see these two together."
    assert series[0].image.startswith("https://thebeacon.film/_vercel/image?url=")
    assert series[0].image_fallback.endswith("/TB_DOUBLEFEATURES.jpeg")
    assert programs[0].description.startswith("António Reis and Margarida Cordeiro")
    assert all(p.happening for p in posts)  # never in Latest News
    for post in posts:
        post.validate()


def test_past_pages_are_read_once_and_failures_retried():
    cache = {}
    first = Http(fail={"https://thebeacon.film/series/double-features"})
    posts = beacon_past.fetch(Context(http=first, today=TODAY, cache=cache))
    assert len(first.pages) == 5
    assert next(p for p in posts if p.category == "Series").image is None  # no picture this time
    second = Http()
    beacon_past.fetch(Context(http=second, today=date(2027, 6, 1), cache=cache))
    assert second.pages == ["https://thebeacon.film/series/double-features"]  # only the one that failed


def test_series_take_the_last_month_they_were_seen_playing():
    cache = {}
    beacon_past.fetch(Context(http=Http(), today=TODAY, cache=cache))  # Shadowland is playing in November
    assert cache["seen:https://thebeacon.film/series/shadowland"]["data"] == "2026-11-01"
    moved = load("beacon_series.html").replace('<a href="/series/shadowland"', '<a href="/series/another"', 1)
    moved = moved.replace('<a href="/series/double-features"',
                                               '<a href="/series/shadowland" class="card"><h3 class="card-title">SHADOWLAND</h3></a>'
                                               '<a href="/series/double-features"')

    class Later(Http):
        def get_text(self, url, **kwargs):
            return moved if url == beacon.SERIES_URL else super().get_text(url, **kwargs)

    posts = beacon_past.fetch(Context(http=Later(), today=date(2027, 1, 10), cache=cache))
    shadowland = next(p for p in posts if p.title == "Shadowland")
    assert shadowland.published == "2026-11-01" and shadowland.date_label == "November 2026"


def test_past_page_order_and_archive_is_not_capped():
    posts = beacon_past.fetch(Context(http=Http(), today=TODAY, cache={}))
    template = posts[1].to_dict()
    stored = [{**template, "id": f"beacon_past|/programs/old{i}", "title": f"Old {i}", "published": "2020-01-01"}
              for i in range(run.POSTS_PER_SOURCE + 5)]
    merged = run.merge_posts(posts, stored, "2026-11-15T12:00:00-08:00", cap=beacon_past.MAX_POSTS)
    assert len(merged) == len(posts) + run.POSTS_PER_SOURCE + 5
    past = build.build_past(merged)["items"]
    shown = [i["title"] for i in past]
    assert "Old 0" not in shown  # no longer on the Beacon's page (listed is False)
    assert [i["when"] for i in past[:4]] == ["May 2026", "May 2026", "April 2026", "November 2025"]
    assert past[-1]["title"] == "Double Features" and past[-1]["when"] == ""  # undated series last
    assert past[0]["image"] and past[0]["description"]
    # Past items stay out of News (the build drops happening items) and out of Happening Now.
    assert all(p["happening"] for p in merged)
    features = build.build_features(merged, [], TODAY)
    assert features["lead"] == [] and features["row"] == []
