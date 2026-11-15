"""The Beacon's series and programs, listed on the Posts page as SERIES / PROGRAM.

- https://thebeacon.film/programs: cards grouped under Now Playing, Coming Soon and
  Past Programs, each with a month ("NOVEMBER 2026"). The month is the post's date
  (its first day, for sorting); the page shows the month itself.
- https://thebeacon.film/series: cards under Now Playing and Past Series. Series have
  no date anywhere, so only the ones under Now Playing are kept, marked as current
  (decided with Elijah 2026-11-15: they lead the feed, past series are left out).

Now-playing series and programs also feed the "At the Beacon" block on the
listings page (scrapers/build.py writes docs/data/features.json). Each keeps its
card image URL; for programs, the program page is read (cached a week) to count
its films for the byline.
"""
from __future__ import annotations

import re
import sys
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..context import Context
from ..models import Post
from ..util import clean_ws, title_case_if_all_caps

SOURCE_ID = "beacon"
SOURCE_NAME = "The Beacon"
BASE_URL = "https://thebeacon.film"
PROGRAMS_URL = BASE_URL + "/programs"
SERIES_URL = BASE_URL + "/series"

MONTHS = {name: i for i, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_MONTH_RE = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


def _sections(html: str, what: str):
    soup = BeautifulSoup(html, "html.parser")
    sections = soup.select("section.listing-section")
    if not sections:
        raise ParseError(f"no sections on the {what} page; layout may have changed")
    for section in sections:
        heading = section.select_one("h2")
        yield clean_ws(heading.get_text()) if heading else "", section.select("a.card[href]")


def card_images(card) -> tuple[str | None, str | None]:
    """The card's image: (resized copy on thebeacon.film, original file). Both are the
    Beacon's own URLs; the site loads them from there and never copies them."""
    img = card.select_one("img[src]")
    if img is None:
        return None, None
    resized = urljoin(BASE_URL + "/", img["src"])
    original = (parse_qs(urlparse(resized).query).get("url") or [None])[0]
    return resized, original if original and original.startswith("https://") else None


def count_films(html: str) -> int:
    """Program page -> number of different films linked under it."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup
    return len({a["href"].split("?")[0] for a in main.select('a[href*="/calendar/movie/"]')})


def _sentence(text: str) -> str:
    """'SLOW CINEMA AND ITS REVERBERATIONS.' -> 'Slow cinema and its reverberations.'"""
    text = clean_ws(text)
    if text and text.isupper():
        text = text[0] + text[1:].lower()
    return text


def parse_programs(html: str) -> list[Post]:
    posts = []
    for heading, cards in _sections(html, "programs"):
        status = heading.lower()
        for card in cards:
            title = card.select_one(".card-title")
            meta = card.select_one(".card-meta")
            match = _MONTH_RE.match(clean_ws(meta.get_text()) if meta else "")
            if title is None or not match or match.group(1).lower() not in MONTHS:
                continue  # no readable month: no date, so not listed
            month, year = MONTHS[match.group(1).lower()], int(match.group(2))
            image, fallback = card_images(card)
            posts.append(Post(
                source=SOURCE_ID,
                source_name=SOURCE_NAME,
                title=title_case_if_all_caps(clean_ws(title.get_text())),
                url=BASE_URL + card["href"],
                published=f"{year:04d}-{month:02d}-01",
                date_label=f"{match.group(1).capitalize()} {year}",
                category="Program",
                summary={"now playing": "Now playing.", "coming soon": "Coming soon."}.get(status, ""),
                now_playing=status == "now playing",
                image=image,
                image_fallback=fallback,
            ))
    return posts


def parse_series(html: str) -> list[Post]:
    posts = []
    for heading, cards in _sections(html, "series"):
        if heading.lower() != "now playing":
            continue
        for card in cards:
            title = card.select_one(".card-title")
            meta = card.select_one(".card-meta")
            if title is None:
                continue
            image, fallback = card_images(card)
            tagline = _sentence(meta.get_text()) if meta else ""
            posts.append(Post(
                source=SOURCE_ID,
                source_name=SOURCE_NAME,
                title=title_case_if_all_caps(clean_ws(title.get_text())),
                url=BASE_URL + card["href"],
                published=None,
                date_label="Now playing",
                category="Series",
                summary=tagline,
                current=True,
                now_playing=True,
                image=image,
                image_fallback=fallback,
                byline=tagline or None,
            ))
    return posts


def fetch(ctx: Context) -> list[Post]:
    programs = ctx.http.get_text(PROGRAMS_URL)
    ctx.save_fixture("beacon_programs.html", programs)
    series = ctx.http.get_text(SERIES_URL)
    ctx.save_fixture("beacon_series.html", series)
    programs_now = parse_programs(programs)
    for post in programs_now:
        if not post.now_playing:
            continue
        def load(url=post.url):
            try:
                return count_films(ctx.http.get_text(url))
            except requests.HTTPError as error:  # only the film count is lost
                print(f"[posts/beacon] program page skipped: {error}", file=sys.stderr)
                return 0
        films = ctx.cached(post.url, load)
        post.byline = f"{films} films" if films > 1 else ("1 film" if films == 1 else None)
    return parse_series(series) + programs_now
