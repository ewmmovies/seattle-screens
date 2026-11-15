"""SIFF Programs & Events (Happening Now, added 2026-11-15): https://www.siff.net/programs-and-events.

The page groups cards under FILM FESTIVALS, FILM SERIES, CINEMA PROGRAMS and Grant
Programs (skipped). Each card has a title link, an image and a short blurb. There
are no dates, and the program pages do not list their films, so whether an item is
happening now is decided by the build: it must have a screening in the next three
weeks whose series name matches (scrapers/build.py).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..context import Context
from ..models import Post
from ..util import clean_ws
from .beacon import first_sentences

SOURCE_ID = "siff_programs"
SOURCE_NAME = "SIFF"
BASE_URL = "https://www.siff.net"
PAGE_URL = BASE_URL + "/programs-and-events"

SECTIONS = {"film festivals": "Festival", "film series": "Series", "cinema programs": "Program"}


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


def parse_page(html: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []
    found_section = False
    for heading in soup.find_all("h2"):
        kind = SECTIONS.get(clean_ws(heading.get_text()).lower())
        if kind is None:
            continue
        found_section = True
        container = heading.parent
        for box in container.select(".featured-box"):
            link = box.select_one(".h3 a[href], h3 a[href]")
            if link is None:
                continue
            img = box.select_one("img[src]")
            blurb = box.select_one(".content")
            posts.append(Post(
                source=SOURCE_ID,
                source_name=SOURCE_NAME,
                venue_label="SIFF",
                title=clean_ws(link.get_text()),
                url=urljoin(BASE_URL + "/", link["href"]),
                category=kind,
                happening=True,
                summary="",
                byline=first_sentences(blurb.get_text(" "), most=1, limit=180) if blurb else None,
                image=urljoin(BASE_URL + "/", img["src"]) if img else None,
            ))
    if not found_section:
        raise ParseError("no program sections found; page layout may have changed")
    return posts


def fetch(ctx: Context) -> list[Post]:
    html = ctx.http.get_text(PAGE_URL)
    ctx.save_fixture("siff_programs.html", html)
    return parse_page(html)
