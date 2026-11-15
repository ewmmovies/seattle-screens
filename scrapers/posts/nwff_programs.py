"""NWFF festivals and series (Happening Now, added 2026-11-15).

https://nwfilmforum.org/festivals/ and https://nwfilmforum.org/series/ each list
cards (a.series-preview) under "Current" and "Past" headings; only Current is read.
NWFF's "Current" includes festivals that are not on now, so the build keeps an
item only if it has a screening in the next three weeks whose series matches
(the NWFF listings carry the same series names). Images are NWFF's wide banners;
the site crops them to fill its 16:9 tiles.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..context import Context
from ..models import Post
from ..util import clean_ws
from .beacon import first_sentences

SOURCE_ID = "nwff_programs"
SOURCE_NAME = "Northwest Film Forum"
FESTIVALS_URL = "https://nwfilmforum.org/festivals/"
SERIES_URL = "https://nwfilmforum.org/series/"


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


def parse_page(html: str, kind: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    current_heading = next((h for h in soup.find_all("h3") if clean_ws(h.get_text()) == "Current"), None)
    if current_heading is None:
        raise ParseError(f"no 'Current' heading on the {kind.lower()} page; layout may have changed")
    posts: list[Post] = []
    for node in current_heading.find_all_next(["h3", "a"]):
        if node.name == "h3":
            break  # "Past" (or anything after Current) ends the list
        if "series-preview" not in (node.get("class") or []) or not node.get("href"):
            continue
        title = node.select_one(".series-preview__title")
        image = node.select_one(".series-preview__image")
        blurb = node.select_one(".series-preview__description")
        counts = [clean_ws(i.get_text()) for i in node.select(".series-preview__counts__item")]
        if title is None:
            continue
        posts.append(Post(
            source=SOURCE_ID,
            source_name=SOURCE_NAME,
            venue_label="NWFF",
            title=clean_ws(title.get_text()),
            url=node["href"],
            category=kind,
            happening=True,
            summary=" · ".join(counts),
            byline=first_sentences(blurb.get_text(" "), most=1, limit=180) if blurb else None,
            image=(image.get("component-graceful-image-load") or None) if image else None,
            image_fallback=(image.get("mobile-url") or None) if image else None,
        ))
    return posts


def fetch(ctx: Context) -> list[Post]:
    festivals = ctx.http.get_text(FESTIVALS_URL)
    ctx.save_fixture("nwff_festivals.html", festivals)
    series = ctx.http.get_text(SERIES_URL)
    ctx.save_fixture("nwff_series.html", series)
    return parse_page(festivals, "Festival") + parse_page(series, "Series")
