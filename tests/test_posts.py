"""Offline tests for the posts scrapers (NWFF news, SIFF blog and press releases)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scrapers import build, run
from scrapers.posts import nwff, siff

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


def test_feed_end_to_end(tmp_path):
    """Runner stores both feeds; build merges them newest first, undated posts by first-seen date."""
    release_dates = {"https://www.siff.net/media/news/pr-doc-grant-awardees-2026": "9/22/2026"}

    class Http:
        request_count = 0

        def get_text(self, url, **kwargs):
            if url in release_dates:
                return f'<p class="small"> {release_dates[url]} <br></p>'
            if "/media/news/" in url:
                return "<p>No date on this page</p>"
            return load({nwff.NEWS_URL: "nwff_news.html", siff.BLOG_URL: "siff_blog.html",
                         siff.NEWS_URL: "siff_news.html"}[url])

    code = run.run(sources=[], post_sources=[nwff, siff], data_dir=tmp_path / "data", venue_ids=set(), http=Http())
    assert code == 0
    status = json.loads((tmp_path / "data" / "status.json").read_text())["posts"]
    assert status["nwff"]["ok"] and status["siff"]["count"] == 5
    site = tmp_path / "docs" / "data"
    build.build(tmp_path / "data", site)
    posts = json.loads((site / "posts.json").read_text())["posts"]
    assert len(posts) == 8
    cache = json.loads((tmp_path / "data" / "cache" / "posts_siff.json").read_text())
    assert len(cache) == 2  # release dates are remembered between runs
    grant = next(p for p in posts if "Courageous" in p["title"])
    assert grant["published"] == "2026-09-22"  # read from the release's own page
    # The release with no readable date falls back to today's first-seen date, so it leads.
    assert posts[0]["published"] is None and posts[0]["category"] == "Press release"
    dated = [p["published"] for p in posts if p["published"]]
    assert dated == sorted(dated, reverse=True)
