"""The Beacon's series and programs, listed on the Posts page as SERIES / PROGRAM.

- https://thebeacon.film/programs: cards grouped under Now Playing, Coming Soon and
  Past Programs, each with a month ("NOVEMBER 2026"). The month is the post's date
  (its first day, for sorting); the page shows the month itself.
- https://thebeacon.film/series: cards under Now Playing and Past Series. Series have
  no date anywhere, so only the ones under Now Playing are kept, marked as current
  (decided with Elijah 2026-11-15: they lead the feed, past series are left out).

Now-playing series and programs also feed the "At the Beacon" block on the
listings page (scrapers/build.py writes docs/data/features.json). Each keeps its
card image URL. Its own page is read (cached a week) for the first one or two
sentences of its description (kept to about two lines on the site; the page
clamps anything longer with an ellipsis) and its list of films; programs show the film count. The
"Scheduled" months are the first and last month in which those films appear on
the Beacon's calendar from today on. The Beacon publishes no start or end dates,
and the calendar lists only upcoming screenings, so for a series that began
earlier the range starts at the current month.
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


def film_urls(html: str) -> list[str]:
    """Series or program page -> its films' calendar pages (absolute, no query)."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup
    urls = []
    for link in main.select('a[href*="/calendar/movie/"]'):
        url = urljoin(BASE_URL + "/", link["href"].split("?")[0])
        if url not in urls:
            urls.append(url)
    return urls


def count_films(html: str) -> int:
    """Program page -> number of different films linked under it."""
    return len(film_urls(html))


_SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)]*\s+(?=[A-Z0-9\"“‘(])")


def first_sentences(text: str, most: int = 4, limit: int = 420) -> str:
    """The first one to four sentences, stopping before ~420 characters."""
    sentences = [s.strip() for s in _SENTENCE_END.split(clean_ws(text)) if s.strip()]
    kept: list[str] = []
    for sentence in sentences[:most]:
        if kept and len(" ".join(kept + [sentence])) > limit:
            break
        kept.append(sentence)
    out = " ".join(kept)
    return out if len(out) <= limit + 200 else out[: limit].rsplit(" ", 1)[0] + "…"


# The top slot shows at most two lines of description (~85 characters a line on a
# desktop). A second sentence is added only if both fit in that; a first sentence
# that is longer on its own is kept whole and the page ends it with an ellipsis.
LEAD_LIMIT = 165


def lead_description(text: str) -> str:
    """The Beacon's own words: the first sentence, plus the second if both fit in two lines."""
    sentences = [s.strip() for s in _SENTENCE_END.split(clean_ws(text)) if s.strip()]
    if not sentences:
        return ""
    kept = sentences[0]
    if len(sentences) > 1 and len(kept) + 1 + len(sentences[1]) <= LEAD_LIMIT:
        kept += " " + sentences[1]
    return kept


def parse_detail(html: str) -> dict:
    """Series or program page -> {'description': one or two sentences, 'films': [calendar URLs]}."""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".entry-description")
    return {"description": lead_description(node.get_text(" ")) if node else "", "films": film_urls(html)}


def month_range(dates: list[str]) -> str | None:
    """['2026-11-15', '2027-01-04'] -> 'November 2026 – January 2027'."""
    if not dates:
        return None
    names = [None, "January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
    label = lambda d: f"{names[int(d[5:7])]} {d[:4]}"  # noqa: E731
    first, last = label(min(dates)), label(max(dates))
    return first if first == last else f"{first} – {last}"


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
                happening=True,
                venue_label="The Beacon",
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
                happening=True,
                venue_label="The Beacon",
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
    posts = parse_series(series) + parse_programs(programs)
    now = [p for p in posts if p.now_playing]
    if not now:
        return posts

    # Scheduled dates for every film, from the full calendar (one request).
    scheduled: dict[str, list[str]] = {}
    try:
        from ..sources.beacon import CALENDAR_URL, parse_calendar
        for entry in parse_calendar(ctx.http.get_text(CALENDAR_URL), ctx.today):
            scheduled.setdefault(entry.url, []).append(entry.date)
    except Exception as error:  # noqa: BLE001 - only the month range is lost
        print(f"[posts/beacon] calendar unavailable, no month ranges: {error}", file=sys.stderr)

    for post in now:
        def load(url=post.url):
            try:
                return parse_detail(ctx.http.get_text(url))
            except requests.HTTPError as error:  # only the description and film list are lost
                print(f"[posts/beacon] page skipped: {error}", file=sys.stderr)
                return {"description": "", "films": []}
        detail = ctx.cached("detail2:" + post.url, load)  # "2": re-read after the 2026-11-15 encoding and length fixes
        films = detail.get("films") or []
        post.description = detail.get("description") or None
        dates = [d for f in films for d in scheduled.get(f, []) if d >= ctx.today.isoformat()]
        post.months = month_range(dates) or (post.date_label if post.category == "Program" else None)
        post.next_date = min(dates) if dates else None
        if post.category == "Program":
            post.byline = f"{len(films)} films" if len(films) > 1 else ("1 film" if films else None)
    return posts
