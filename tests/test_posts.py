"""Offline tests for the posts scrapers (NWFF news, SIFF blog and press releases)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scrapers import build, run
from datetime import date

from scrapers.posts import beacon, nwff, siff, tasveer

FIXTURES = Path(__file__).parent / "fixtures" / "posts"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_nwff_news():
    posts = nwff.parse_news(load("nwff_news.html"))
    assert len(posts) == 3
    first = posts[0]
    assert first.to_dict() == {
        "id": "nwff|/news/local-sightings-film-festival-2026-jury-award-winners/",
        "source": "nwff",
        "source_name": "Northwest Film Forum",
        "title": "Local Sightings Film Festival 2026 Announces Jury Award Winners for Best Feature & Short Films",
        "url": "https://nwfilmforum.org/news/local-sightings-film-festival-2026-jury-award-winners/",
        "published": "2026-10-08",
        "category": "News",
        "summary": first.summary,
        "first_seen": None,
        "date_label": None,
        "current": False,
        "now_playing": False,
        "image": None,
        "image_fallback": None,
        "byline": None,
        "description": None,
        "months": None,
    }
    assert len(first.summary) <= 240 and first.summary.endswith("…")
    assert first.summary.startswith("Seattle, WA – Northwest Film Forum")
    for post in posts:
        post.validate()


def test_siff_blog():
    posts = siff.parse_blog(load("siff_blog.html"))
    assert [p.title for p in posts] == ["Film Notes: Pierrot le Fou (1965)", "Film Notes: A Man and A Woman (1966)",
                                        "November 2026 at SIFF Cinemas"]
    nov = posts[2]
    assert nov.url == "https://www.siff.net/media/blog/november-2026-at-siff-cinemas"
    assert nov.published == "2026-10-30" and nov.category == "Cinema"
    assert nov.summary == "With the new month we welcome a new lineup of films, events, and more. See what's happening this November at SIFF Cinemas."
    assert "Cinema" not in posts[0].summary[:10]  # the category label is not part of the summary


def test_siff_press_releases_have_no_date():
    posts = siff.parse_news(load("siff_news.html"))
    assert len(posts) == 2
    assert all(p.published is None and p.category == "Press release" for p in posts)
    assert "More Details" not in posts[0].summary


def test_press_release_date_from_its_own_page():
    page = '<div class="col-md-8"><p class="small">\n 9/22/2026\n <br>\n </p><div class="body-copy">x</div></div>'
    assert siff.parse_release_date(page) == "2026-09-22"
    assert siff.parse_release_date("<p class='small'>Photo credit</p>") is None


def test_layout_change_is_an_error():
    with pytest.raises(nwff.ParseError):
        nwff.parse_news("<html><body>new site</body></html>")
    with pytest.raises(siff.ParseError):
        siff.parse_blog("<html><body>new site</body></html>")


TODAY = date(2026, 11, 15)


def test_beacon_programs_and_series():
    programs = beacon.parse_programs(load("beacon_programs.html"))
    assert len(programs) == 7
    first = programs[0]
    assert first.title == "Surplus Reality: How William Greaves Constructed a Stage, Sabotaged It and Mined Truth Out of the Wreckage"
    assert (first.published, first.date_label, first.category, first.summary) == ("2026-11-01", "November 2026", "Program", "Now playing.")
    assert programs[2].summary == "Coming soon."
    series = beacon.parse_series(load("beacon_series.html"))
    assert [s.title for s in series] == ["Time as a Symptom", "Shadowland"]  # past series left out
    assert series[0].current and series[0].published is None and series[0].category == "Series"
    assert series[0].summary == "Slow cinema and its reverberations."
    for post in programs + series:
        post.validate()


def test_beacon_card_images_and_film_count():
    series = beacon.parse_series(load("beacon_series.html"))
    assert series[0].image == ("https://thebeacon.film/_vercel/image?url=https%3A%2F%2Fv4sbluaw4a7zyg44.public.blob.vercel-storage.com"
                               "%2Fbeacon%2Fcommon%2FTB_TIMEASASYMPTOM_%25281%2529.png&w=2048&q=78&dpl=dpl_5qcamuCPnGAeaZE5f9ddUz7NM7zs")
    assert series[0].image_fallback == "https://v4sbluaw4a7zyg44.public.blob.vercel-storage.com/beacon/common/TB_TIMEASASYMPTOM_%281%29.png"
    programs = beacon.parse_programs(load("beacon_programs.html"))
    assert [p.now_playing for p in programs[:3]] == [True, True, False]
    assert programs[3].image is None  # past programs: no image kept in the fixture, none needed
    assert beacon.count_films(load("beacon_program_surplus-reality.html")) == 4


def test_beacon_detail_sentences_and_months():
    detail = beacon.parse_detail(load("beacon_series_shadowland.html"))
    assert detail["films"][0] == "https://thebeacon.film/calendar/movie/the-strange-love-of-martha-ivers"
    assert len(detail["films"]) == 4
    long = ("What happens after all the time is spent? Rather than spending time like it's some debased currency, "
            "the Beacon invites you to hold the heavy body of time in your arms. Slow cinema is not a genre. "
            "It is a style, a mode, a pace. Experiencing time is a symptom of cinema's very essence.")
    kept = beacon.first_sentences(long)
    assert kept.startswith("What happens") and kept.endswith("a pace.")  # four sentences
    assert beacon.month_range(["2026-12-03", "2026-11-15", "2027-01-04"]) == "November 2026 – January 2027"
    assert beacon.month_range(["2026-11-15"]) == "November 2026" and beacon.month_range([]) is None


def test_tasveer_feed():
    posts = tasveer.parse_feed(load("tasveer_feed.xml"))
    assert [p.published for p in posts] == ["2025-06-16", "2024-12-03", "2024-02-13"]
    assert posts[1].title == "19th Tasveer Festival & Market 2024" and posts[0].category == "Blog"
    assert posts[0].url.startswith("https://tasveer.org/desiqueer")


def test_six_month_window_and_order():
    posts = [
        {"id": "a", "title": "Old", "published": "2026-05-14"},
        {"id": "b", "title": "Edge", "published": "2026-05-15"},
        {"id": "c", "title": "New", "published": "2026-11-10"},
        {"id": "d", "title": "Undated", "published": None},
        {"id": "e", "title": "Series", "published": None, "current": True},
        {"id": "f", "title": "Coming", "published": "2026-12-01"},
    ]
    out = [p["title"] for p in build.build_posts(posts, TODAY)["posts"]]
    assert out == ["Series", "Coming", "New", "Edge"]  # current first, then newest first; old and undated dropped


def test_months_before_clamps():
    assert build.months_before(date(2026, 8, 31), 6) == date(2026, 2, 28)
    assert build.months_before(date(2026, 3, 15), 6) == date(2025, 9, 15)


def test_series_stop_being_current_when_they_leave_now_playing():
    stored = [{"id": "beacon|/series/old", "title": "Old", "current": True, "first_seen": "2026-10-01T00:00:00-07:00"}]
    merged = run.merge_posts([], stored, "2026-11-15T00:00:00-08:00")
    assert merged[0]["current"] is False


def test_feed_end_to_end(tmp_path):
    """Runner stores every feed; build keeps the last six months, newest first."""
    release_dates = {"https://www.siff.net/media/news/pr-doc-grant-awardees-2026": "9/22/2026"}
    pages = {nwff.NEWS_URL: "nwff_news.html", siff.BLOG_URL: "siff_blog.html", siff.NEWS_URL: "siff_news.html",
             beacon.PROGRAMS_URL: "beacon_programs.html", beacon.SERIES_URL: "beacon_series.html",
             tasveer.FEED_URL: "tasveer_feed.xml"}

    class Http:
        request_count = 0

        def get_text(self, url, **kwargs):
            if url in release_dates:
                return f'<p class="small"> {release_dates[url]} <br></p>'
            if "/media/news/" in url:
                return "<p>No date on this page</p>"
            if url.startswith(beacon.PROGRAMS_URL + "/"):
                return load("beacon_program_surplus-reality.html")
            if url.startswith(beacon.SERIES_URL + "/"):
                return load("beacon_series_shadowland.html")
            if url == "https://thebeacon.film/calendar":
                return (Path(__file__).parent / "fixtures" / "beacon" / "calendar.html").read_text(encoding="utf-8")
            return load(pages[url])

    code = run.run(sources=[], post_sources=[beacon, nwff, siff, tasveer], data_dir=tmp_path / "data",
                   venue_ids=set(), http=Http(), today=TODAY)
    assert code == 0
    status = json.loads((tmp_path / "data" / "status.json").read_text())["posts"]
    assert all(status[s]["ok"] for s in ("beacon", "nwff", "siff", "tasveer"))
    cache = json.loads((tmp_path / "data" / "cache" / "posts_siff.json").read_text())
    assert len(cache) == 2  # release dates are remembered between runs

    site = tmp_path / "docs" / "data"
    build.build(tmp_path / "data", site, TODAY)
    posts = json.loads((site / "posts.json").read_text())["posts"]
    titles = [p["title"] for p in posts]
    assert titles[:2] == ["Shadowland", "Time as a Symptom"]  # current series lead
    dated = [p["published"] for p in posts[2:]]
    assert dated == sorted(dated, reverse=True) and min(dated) >= "2026-05-15"
    assert not any(p["source"] == "tasveer" for p in posts)  # newest Tasveer post is June 2025
    assert not any(p["published"] is None and not p.get("current") for p in posts)  # undated release dropped
    assert "SIFF announces winning projects of 2026 Courageous Documentary Filmmaking Grants" in titles
    assert "NWFF Announces Recipients, Jurors, for Collective Power Fund 2025" not in titles  # January: too old

    features = json.loads((site / "features.json").read_text())["features"]
    assert [(f["kind"], f["title"]) for f in features] == [
        ("Series", "Shadowland"), ("Series", "Time as a Symptom"),
        ("Program", "Surplus Reality: How William Greaves Constructed a Stage, Sabotaged It and Mined Truth Out of the Wreckage"),
        ("Program", "The Very Living End: Frank Tashlin and the American Nervous Breakdown"),
    ]  # series first, at most four, Coming Soon left out
    assert features[0]["byline"] == "The emotional otherworlds of classic cinema."
    assert features[2]["byline"] == "4 films" and features[2]["when"] == "November 2026"
    assert features[0]["description"] == ("The emotional otherworlds of classic cinema. "
                                          "Unspooling the ribbon of dreams every Sunday afternoon.")
    # Martha Ivers (in Shadowland) is on the calendar fixture on Nov 15 and 16 only.
    assert features[0]["months"] == "November 2026"
    assert features[2]["description"] == ""  # this program's page has no description
    assert features[0]["image"].startswith("https://thebeacon.film/_vercel/image?url=")
    assert features[0]["image_fallback"] == "https://v4sbluaw4a7zyg44.public.blob.vercel-storage.com/beacon/common/TB_SHADOWLAND2.png"
