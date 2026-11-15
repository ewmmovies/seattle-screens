"""North Bend Theatre.

Same layout as siff.py: constants, pure parsing, cleaning, then fetch().

Source: ThunderTix. https://tix.northbendtheatre.com/ lists every event under
category headings (an event can sit under more than one). Each event page
prints its date and time ("November 15th, 2026 @ 3:00pm PST"); that line is
the only one trusted. Titles and web addresses also carry a day and time, and
they are sometimes wrong (one 3pm show's address says 7pm).

Event pages are cached for a week; one page = one showing.

Run by itself to see live output:  python -m scrapers.sources.north_bend
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from ..context import Context
from ..models import Screening, Showtime, merge_screenings
from ..util import clean_ws, match_key, parse_hm_minutes, title_case_if_all_caps

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "north_bend"
VENUE_IDS = ["north-bend"]

BASE_URL = "https://tix.northbendtheatre.com"
INDEX_URL = BASE_URL + "/"

# Categories that are not a series. "Free Shows!" becomes a note instead.
GENERIC_CATEGORIES = {"free shows!", "show all categories", "all events", "upcoming events"}
FREE_CATEGORY = "free shows!"
# Categories whose events are not films: shown as "Live event".
NON_FILM_CATEGORIES = {"live comedy", "seattle international comedy competition"}

_DATE_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,\s+(\d{4})\s*@\s*(\d{1,2}:\d{2}\s*[ap]m)", re.IGNORECASE)
_TRAILING_WHEN_RE = re.compile(r"\s*\((?:[^()]*\b(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b[^()]*|[^()]*@\s*\d[^()]*)\)\s*$", re.IGNORECASE)
_YEAR_RUNTIME_RE = re.compile(r"\b((?:18|19|20)\d{2})\s*\[[^\]]*\]\s*((?:\d+\s*h)?\s*(?:\d+\s*m)?)", re.IGNORECASE)


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing
# --------------------------------------------------------------------------


@dataclass
class Listing:
    url: str
    title: str  # as listed, with the "(Sunday Nov. 15th @3pm)" tail
    categories: list[str] = field(default_factory=list)


def parse_index(html: str) -> list[Listing]:
    """Index page -> one Listing per event URL, with every category it appears under."""
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("#categoriesPageEventsList div.categoryBlock")
    if not blocks:
        raise ParseError("no category list found; page layout may have changed")
    listings: dict[str, Listing] = {}
    for block in blocks:
        heading = block.select_one(".categoryTitle")
        category = clean_ws(heading.get_text()) if heading else ""
        for link in block.select('div.title a[href^="/event/"]'):
            url = BASE_URL + link["href"]
            listing = listings.setdefault(url, Listing(url=url, title=clean_ws(link.get_text())))
            if category and category not in listing.categories:
                listing.categories.append(category)
    return list(listings.values())


def parse_event(html: str) -> dict:
    """Event page -> {'date', 'time', 'year', 'runtime_min'}."""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("#dateAndTitle .date") or soup.select_one("#dateAndTimeContainer .sectionContent")
    match = _DATE_RE.search(clean_ws(node.get_text()) if node else "")
    if not match:
        raise ParseError("event page has no readable date line")
    month, day, year, clock = match.groups()
    try:
        when = datetime.strptime(f"{month} {day} {year} {clock.replace(' ', '').upper()}", "%B %d %Y %I:%M%p")
    except ValueError as error:
        raise ParseError(f"unreadable date {match.group(0)!r}") from error

    description = soup.select_one("#descriptionContainer .sectionContent")
    film_year = runtime = None
    if description:
        found = _YEAR_RUNTIME_RE.search(clean_ws(description.get_text(" ")))
        if found:
            film_year = int(found.group(1))
            runtime = parse_hm_minutes(found.group(2))
    return {"date": when.date().isoformat(), "time": when.strftime("%H:%M"),
            "year": film_year, "runtime_min": runtime}


# --------------------------------------------------------------------------
# 3. Cleaning
# --------------------------------------------------------------------------


def clean_title(title: str) -> str:
    """'Mrs. Miniver (Sunday Nov. 15th @3pm)' -> 'Mrs. Miniver'."""
    return title_case_if_all_caps(_TRAILING_WHEN_RE.sub("", title).strip())


def build_screenings(listings: list[Listing], events: dict[str, dict]) -> list[Screening]:
    records = []
    for listing in listings:
        event = events.get(listing.url)
        if not event:
            continue
        title = clean_title(listing.title)
        lowered = [c.lower() for c in listing.categories]
        series = next((c for c in listing.categories
                       if c.lower() not in GENERIC_CATEGORIES and match_key(c) != match_key(title)), None)
        records.append(Screening(
            venue_id="north-bend",
            date=event["date"],
            title=title,
            kind="event" if any(c in NON_FILM_CATEGORIES for c in lowered) else "film",
            series=series,
            year=event.get("year"),
            runtime_min=event.get("runtime_min"),
            notes=["Free admission"] if FREE_CATEGORY in lowered else [],
            url=listing.url,
            showtimes=[Showtime(time=event["time"], ticket_url=listing.url)],
        ))
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def fetch(ctx: Context) -> list[Screening]:
    html = ctx.http.get_text(INDEX_URL)
    ctx.save_fixture("index.html", html)
    listings = parse_index(html)
    if not listings:
        return []

    events: dict[str, dict] = {}
    for listing in listings:
        def load(url=listing.url):
            try:
                page = ctx.http.get_text(url)
            except requests.HTTPError as error:  # a withdrawn event should not sink the venue
                print(f"[north_bend] event page skipped: {error}", file=sys.stderr)
                return {}
            if not events:
                ctx.save_fixture("event_" + url.rsplit("/", 1)[-1] + ".html", page)
            return parse_event(page)
        events[listing.url] = ctx.cached(listing.url, load)

    first = ctx.today.isoformat()
    last = (ctx.today + timedelta(days=ctx.horizon_days)).isoformat()
    events = {url: e for url, e in events.items() if e and first <= e["date"] <= last}
    return build_screenings(listings, events)


if __name__ == "__main__":  # manual check: python -m scrapers.sources.north_bend
    context = Context(horizon_days=21)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
