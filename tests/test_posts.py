"""Offline tests for the posts scrapers (NWFF news, SIFF blog and press releases)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scrapers import build, run
from datetime import date

from scrapers.posts import beacon, nwff, nwff_programs, siff, siff_programs

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
        "coming_soon": False,
        "image": None,
        "image_fallback": None,
        "byline": None,
        "description": None,
        "months": None,
        "happening": False,
        "venue_label": None,
        "next_date": None,
        "listed": True,
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
    with_contact = '<p class="small">\n 5/17/2026\n <br>\n press@siff.net</p>'  # most releases look like this
    assert siff.parse_release_date(with_contact) == "2026-05-17"
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
    # Top slot: the Beacon's own words, one or two sentences that fit in two lines.
    assert beacon.lead_description(long) == "What happens after all the time is spent?"  # 2nd would overflow
    two = "The emotional otherworlds of classic cinema. Unspooling the ribbon of dreams every Sunday afternoon. More."
    assert beacon.lead_description(two) == two.rsplit(" ", 1)[0]
    one = "A single very long opening sentence " + "that keeps going " * 12 + "until it ends. Second."
    assert beacon.lead_description(one) == one.rsplit(" ", 1)[0]  # kept whole; the page adds the ellipsis
    assert beacon.month_range(["2026-12-03", "2026-11-15", "2027-01-04"]) == "November 2026 – January 2027"
    assert beacon.month_range(["2026-11-15"]) == "November 2026" and beacon.month_range([]) is None


def test_twelve_month_window_and_order():
    posts = [
        {"id": "a", "title": "Old", "published": "2025-11-14"},
        {"id": "b", "title": "Edge", "published": "2025-11-15"},
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
    """Runner stores every feed; build keeps the last twelve months, newest first."""
    release_dates = {"https://www.siff.net/media/news/pr-doc-grant-awardees-2026": "9/22/2026"}
    pages = {nwff.NEWS_URL: "nwff_news.html", siff.BLOG_URL: "siff_blog.html", siff.NEWS_URL: "siff_news.html",
             beacon.PROGRAMS_URL: "beacon_programs.html", beacon.SERIES_URL: "beacon_series.html"}

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

    code = run.run(sources=[], post_sources=[beacon, nwff, siff], data_dir=tmp_path / "data",
                   venue_ids=set(), http=Http(), today=TODAY)
    assert code == 0
    status = json.loads((tmp_path / "data" / "status.json").read_text())["posts"]
    assert all(status[s]["ok"] for s in ("beacon", "nwff", "siff"))
    cache = json.loads((tmp_path / "data" / "cache" / "posts_siff.json").read_text())
    assert len(cache) == 2  # release dates are remembered between runs

    site = tmp_path / "docs" / "data"
    build.build(tmp_path / "data", site, TODAY)
    posts = json.loads((site / "posts.json").read_text())["posts"]
    titles = [p["title"] for p in posts]
    assert "Shadowland" not in titles  # series and programs live under Happening Now
    dated = [p["published"] for p in posts]
    assert dated == sorted(dated, reverse=True) and min(dated) >= "2025-11-15"
    assert not any(p["published"] is None and not p.get("current") for p in posts)  # undated release dropped
    assert "SIFF announces winning projects of 2026 Courageous Documentary Filmmaking Grants" in titles
    assert "NWFF Announces Recipients, Jurors, for Collective Power Fund 2025" in titles  # January: inside 12 months

    features = json.loads((site / "features.json").read_text())
    # No SIFF/NWFF screenings in this run, so the row holds only the Beacon's programs.
    assert [f["title"] for f in features["lead"]] == ["Shadowland", "Time as a Symptom", "Love Is a Country of Two and Trespassers Will Be Shot!"]
    assert [f["kind"] for f in features["row"]] == ["Program", "Program"]
    lead = features["lead"][0]
    assert lead["description"] == ("The emotional otherworlds of classic cinema. "
                                   "Unspooling the ribbon of dreams every Sunday afternoon.")
    assert lead["months"] == "November 2026"  # Martha Ivers is on the calendar fixture on Nov 15 and 16
    assert lead["image"].startswith("https://thebeacon.film/_vercel/image?url=")
    assert lead["image_fallback"] == "https://v4sbluaw4a7zyg44.public.blob.vercel-storage.com/beacon/common/TB_SHADOWLAND2.png"
    assert features["row"][0]["byline"] == "4 films" and features["row"][0]["when"] == "November 2026"
    assert features["row"][0]["venue"] == "The Beacon"
    # Happening items never appear in Latest News.
    assert not any(p.get("happening") for p in posts)


# --- Happening Now: SIFF Programs & Events, NWFF festivals and series ---------------


def test_siff_programs_page():
    posts = siff_programs.parse_page(load("siff_programs.html"))
    kinds = {p.title: p.category for p in posts}
    assert kinds["Nouvelles Femmes"] == "Series" and kinds["Book Club"] == "Program"
    assert kinds["Seattle International Film Festival"] == "Festival"
    assert "SIFF Grant for Courageous Documentary Filmmaking" not in kinds  # grant section skipped
    nf = next(p for p in posts if p.title == "Nouvelles Femmes")
    assert nf.url == "https://www.siff.net/french-new-wave" and nf.venue_label == "SIFF" and nf.happening
    assert nf.image == "https://www.siff.net/images/CINEMA/2026/Nouvelles%20Femmes/CIN_NouvellesFemmes_Digital_1600x900.png"
    assert nf.byline.startswith("Bursting with exuberant joie de vivre")
    pnw = next(p for p in posts if p.title == "PNW Awards")
    assert pnw.url == "https://www.siff.net/sfcs"
    for post in posts:
        post.validate()


def test_nwff_current_only():
    series = nwff_programs.parse_page(load("nwff_series.html"), "Series")
    assert [p.title for p in series] == ["The Disabled List", "Evergreens", "Truth To Fiction", "Unstreamable"]
    un = series[-1]
    assert un.url == "https://nwfilmforum.org/series/unstreamable-scarecrow-jas-keimig/"
    assert un.image.endswith("series_unstreamable_hero-2550x900.jpg") and un.image_fallback.endswith("-900x318.jpg")
    assert un.byline == ("Unstreamable curates weird, horny, forgotten cinema that, for one reason or another, "
                         "is unavailable on any US streaming service.")
    assert un.venue_label == "NWFF" and un.category == "Series"
    festivals = nwff_programs.parse_page(load("nwff_festivals.html"), "Festival")
    assert [p.title for p in festivals] == ["Cadence Video Poetry Festival", "Local Sightings Film Festival"]
    with pytest.raises(nwff_programs.ParseError):
        nwff_programs.parse_page("<html><h3>Upcoming</h3></html>", "Series")


def test_series_names_match_loosely_but_not_wrongly():
    m = build._names_match
    assert m("Book Club", "SIFF Book Club") and m("Community Screenings", "Community Screening")
    assert m("Local Sightings Film Festival", "Local Sightings Film Festival 2026")
    assert not m("Movie Club", "SIFF Book Club") and not m("Evergreens", "Evergreen Terrace")
    assert not m("SIFF Cinema", "Cinema Italian Style")


def _shot(venue, day, series):
    return {"venue_id": venue, "date": day, "series": series, "title": "x", "showtimes": [{"time": "19:00"}]}


def test_happening_now_layout():
    siff_items = [p.to_dict() for p in siff_programs.parse_page(load("siff_programs.html"))]
    nwff_items = [p.to_dict() for p in nwff_programs.parse_page(load("nwff_series.html"), "Series")]
    nwff_items += [p.to_dict() for p in nwff_programs.parse_page(load("nwff_festivals.html"), "Festival")]
    beacon_items = [p.to_dict() for p in beacon.parse_series(load("beacon_series.html"))
                    + beacon.parse_programs(load("beacon_programs.html"))]
    screenings = [
        _shot("siff-uptown", "2026-11-17", "Nouvelles Femmes"),
        _shot("siff-downtown", "2026-11-20", "SIFF Book Club"),
        _shot("siff-uptown", "2026-12-20", "The Open Road"),        # beyond three weeks: not happening
        _shot("nwff", "2026-11-21", "Unstreamable"),
        _shot("nwff", "2026-11-18", "Truth To Fiction"),
        _shot("siff-uptown", "2026-11-16", "Unstreamable"),         # wrong theater: does not count for NWFF
    ]
    out = build.build_features(siff_items + nwff_items + beacon_items, screenings, TODAY)
    # Series first, then the Coming Soon program; now-playing programs stay in the row.
    assert [c["title"] for c in out["lead"]] == ["Shadowland", "Time as a Symptom", "Love Is a Country of Two and Trespassers Will Be Shot!"]
    assert out["lead"][0]["when"] == "Now playing" and out["lead"][0]["kind"] == "Series"
    assert out["lead"][2]["when"] == "Coming soon" and out["lead"][2]["kind"] == "Program"
    row = [(c["venue"], c["title"], c["when"]) for c in out["row"]]
    assert row == [
        ("SIFF", "Nouvelles Femmes", "Next: Nov 17"),
        ("NWFF", "Truth To Fiction", "Next: Nov 18"),
        ("The Beacon", "Surplus Reality: How William Greaves Constructed a Stage, Sabotaged It and Mined Truth Out of the Wreckage", "November 2026"),
        ("SIFF", "Book Club", "Next: Nov 20"),
        ("NWFF", "Unstreamable", "Next: Nov 21"),
        ("The Beacon", "The Very Living End: Frank Tashlin and the American Nervous Breakdown", "November 2026"),
    ]  # theaters alternate; within a theater, soonest first


def test_no_beacon_series_falls_back_to_a_program():
    programs = [p.to_dict() for p in beacon.parse_programs(load("beacon_programs.html"))]
    out = build.build_features(programs, [], TODAY)  # no series: the Coming Soon program leads alone
    assert [c["title"] for c in out["lead"]] == ["Love Is a Country of Two and Trespassers Will Be Shot!"]
    assert len(out["row"]) == 2  # both now-playing programs
    playing = [p for p in programs if not p["coming_soon"]]
    out = build.build_features(playing, [], TODAY)  # nothing coming either: a now-playing program leads
    assert [c["kind"] for c in out["lead"]] == ["Program"]
    assert len(out["row"]) == 1  # the other now-playing program


def test_coming_soon_moves_to_the_row_once_it_opens():
    programs = [p.to_dict() for p in beacon.parse_programs(load("beacon_programs.html"))]
    love = next(p for p in programs if p["coming_soon"])
    love.update(coming_soon=False, now_playing=True)  # the Beacon has moved it to Now Playing
    series = [p.to_dict() for p in beacon.parse_series(load("beacon_series.html"))]
    out = build.build_features(series + programs, [], TODAY)
    assert "Love Is a Country of Two and Trespassers Will Be Shot!" not in [c["title"] for c in out["lead"]]
    assert "Love Is a Country of Two and Trespassers Will Be Shot!" in [c["title"] for c in out["row"]]


def test_detail_page_image_and_first_sentence():
    detail = beacon.parse_detail(load("beacon_program_love-is-a-country.html"))
    assert detail["image"].startswith("https://thebeacon.film/_vercel/image?url=https%3A%2F%2Fv4sbluaw4a7zyg44")
    assert detail["image_fallback"] == "https://v4sbluaw4a7zyg44.public.blob.vercel-storage.com/programs/1792950181821-zz.png"
    assert detail["films"] == ["https://thebeacon.film/calendar/movie/breathless"]
    past = beacon.parse_detail(load("beacon_program_in-the-midst.html"))
    assert past["first"] == ("António Reis and Margarida Cordeiro together created one of the most influential "
                             "bodies of work in the history of Portuguese cinema.")


def test_items_no_longer_listed_are_dropped():
    item = nwff_programs.parse_page(load("nwff_series.html"), "Series")[-1].to_dict()
    item["listed"] = False
    out = build.build_features([item], [_shot("nwff", "2026-11-21", "Unstreamable")], TODAY)
    assert out["row"] == [] and out["lead"] == []


def test_undated_posts_do_not_push_dated_ones_out_of_the_cap():
    stored = [{"id": f"siff|/u{i}", "title": f"Undated {i}", "published": None,
               "first_seen": "2026-11-15T00:00:00-08:00"} for i in range(run.POSTS_PER_SOURCE)]
    stored.append({"id": "siff|/dated", "title": "Dated", "published": "2026-10-01",
                   "first_seen": "2026-10-02T00:00:00-07:00"})
    merged = run.merge_posts([], stored, "2026-11-15T00:00:00-08:00")
    assert len(merged) == run.POSTS_PER_SOURCE and merged[0]["id"] == "siff|/dated"


def test_unreadable_release_date_is_retried_after_a_week():
    from scrapers.context import Context

    class Http:
        def __init__(self, release):
            self.release, self.calls = release, 0

        def get_text(self, url, **kwargs):
            if url == siff.BLOG_URL:
                return load("siff_blog.html")
            if url == siff.NEWS_URL:
                return load("siff_news.html")
            self.calls += 1
            return self.release

    cache = {}
    first = Http("<p>no date</p>")
    siff.fetch(Context(http=first, today=date(2026, 11, 15), cache=cache))
    same_week = Http('<p class="small">5/17/2026 press@siff.net</p>')
    posts = siff.fetch(Context(http=same_week, today=date(2026, 11, 18), cache=cache))
    assert same_week.calls == 0 and all(p.published is None for p in posts if p.category == "Press release")
    later = Http('<p class="small">5/17/2026 press@siff.net</p>')
    posts = siff.fetch(Context(http=later, today=date(2026, 11, 23), cache=cache))
    assert later.calls == 2 and all(p.published == "2026-05-17" for p in posts if p.category == "Press release")
