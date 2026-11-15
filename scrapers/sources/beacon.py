"""The Beacon (Columbia City).

Same layout as siff.py: constants, pure parsing, cleaning, then fetch().

Source: one server-rendered page holds every upcoming date,
https://thebeacon.film/calendar. It carries two views of the same data, a
month grid and a list; this scraper reads the list (div.cal-list), because
each list day prints its full date ("Sunday, November 15") under a month
heading. The year is not printed: it is chosen so that the printed weekday
matches, which also handles the December-to-January rollover.

Per-film details (director, year, runtime) come from each film page's
schema.org Movie JSON-LD, cached for a week.

Run by itself to see live output:  python -m scrapers.sources.beacon
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from ..context import Context
from ..models import Screening, Showtime, merge_screenings
from ..util import clean_ws, parse_hm_minutes, parse_iso_duration_minutes, parse_time_12h, title_case_if_all_caps

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "beacon"
VENUE_IDS = ["beacon"]

BASE_URL = "https://thebeacon.film"
CALENDAR_URL = BASE_URL + "/calendar"
MOVIE_PATH = "/calendar/movie/"
SKIP_TITLES = {"rent the beacon"}
MONTHS = {name: i for i, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

_DAY_RE = re.compile(r"^([A-Za-z]+),\s+([A-Za-z]+)\s+(\d{1,2})$")


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing
# --------------------------------------------------------------------------


@dataclass
class RawEntry:
    date: str
    time: str
    title: str  # as shown (ALL CAPS on this site)
    url: str
    ticket_url: str | None
    sold_out: bool
    free: bool


def resolve_date(label: str, today: date) -> date:
    """'Sunday, November 15' -> the date with that weekday nearest to today."""
    match = _DAY_RE.match(clean_ws(label))
    if not match:
        raise ParseError(f"unreadable day heading {label!r}")
    weekday, month_name, day = match.group(1).lower(), match.group(2).lower(), int(match.group(3))
    month = MONTHS.get(month_name)
    if month is None:
        raise ParseError(f"unknown month in {label!r}")
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate.strftime("%A").lower() == weekday:
            candidates.append(candidate)
    if not candidates:
        raise ParseError(f"no year makes {label!r} fall on a {match.group(1)}")
    return min(candidates, key=lambda c: abs((c - today).days))


def parse_calendar(html: str, today: date) -> list[RawEntry]:
    soup = BeautifulSoup(html, "html.parser")
    days = soup.select("div.cal-list div.cal-list-day")
    if not days:
        raise ParseError("no days found in the calendar list view; page layout may have changed")
    entries: list[RawEntry] = []
    for day in days:
        label = day.select_one("p.cal-list-date")
        if label is None:
            raise ParseError("calendar day without a date heading")
        when = resolve_date(label.get_text(), today).isoformat()
        for node in day.select("div.cal-list-entry"):
            link = node.select_one("a.cal-list-movie")
            if link is None:
                continue
            title = clean_ws(link.get_text())
            href = link.get("href") or ""
            classes = node.get("class") or []
            if "cal-list-entry-rental" in classes or title.lower() in SKIP_TITLES or not href.startswith(MOVIE_PATH):
                continue  # rental slots and anything that is not a film page
            time_node = node.select_one(".cal-list-time")
            if time_node is None:
                raise ParseError(f"{when} {title!r}: no showtime")
            buy = node.select_one("a.buy-btn")
            sold_out = "sold-out" in classes or node.select_one(".sold-out-btn") is not None
            entries.append(RawEntry(
                date=when,
                time=parse_time_12h(time_node.get_text()),
                title=title,
                url=BASE_URL + href.split("?")[0],
                ticket_url=(BASE_URL + buy["href"]) if buy and buy.get("href", "").startswith("/") else None,
                sold_out=sold_out,
                free=node.select_one(".free-pill") is not None,
            ))
    return entries


def parse_detail(html: str) -> dict:
    """Film page -> {'directors': [...], 'year': int|None, 'runtime_min': int|None}."""
    soup = BeautifulSoup(html, "html.parser")
    movie = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "Movie":
                movie = item
                break
    directors: list[str] = []
    year = runtime = None
    if movie:
        people = movie.get("director") or []
        people = people if isinstance(people, list) else [people]
        directors = [clean_ws(p.get("name")) for p in people if isinstance(p, dict) and clean_ws(p.get("name"))]
        runtime = parse_iso_duration_minutes(movie.get("duration"))
        match = re.match(r"(18|19|20)\d{2}", str(movie.get("datePublished") or ""))
        year = int(match.group()) if match else None
    if runtime is None:  # fall back to the visible "Runtime 116 minutes" line
        match = re.search(r"Runtime\s+([\dhm ]+(?:minutes|min)?)", soup.get_text(" "), re.IGNORECASE)
        runtime = parse_hm_minutes(match.group(1)) if match else None
    return {"directors": directors, "year": year, "runtime_min": runtime}


# --------------------------------------------------------------------------
# 3. Cleaning
# --------------------------------------------------------------------------


def build_screenings(entries: list[RawEntry], details: dict[str, dict]) -> list[Screening]:
    records = []
    for entry in entries:
        info = details.get(entry.url) or {}
        records.append(Screening(
            venue_id="beacon",
            date=entry.date,
            title=title_case_if_all_caps(entry.title),
            directors=list(info.get("directors") or []),
            year=info.get("year"),
            runtime_min=info.get("runtime_min"),
            notes=["Free admission"] if entry.free else [],
            url=entry.url,
            showtimes=[Showtime(time=entry.time, ticket_url=entry.ticket_url, sold_out=entry.sold_out)],
        ))
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def fetch(ctx: Context) -> list[Screening]:
    html = ctx.http.get_text(CALENDAR_URL)
    ctx.save_fixture("calendar.html", html)
    last_day = (ctx.today + timedelta(days=ctx.horizon_days)).isoformat()
    entries = [e for e in parse_calendar(html, ctx.today) if ctx.today.isoformat() <= e.date <= last_day]

    details: dict[str, dict] = {}
    for url in sorted({e.url for e in entries}):
        def load(url=url):
            try:
                page = ctx.http.get_text(url)
            except requests.HTTPError as error:  # one missing film page should not sink the venue
                print(f"[beacon] detail page skipped: {error}", file=sys.stderr)
                return {}
            if not details:
                ctx.save_fixture("movie_" + url.rsplit("/", 1)[-1] + ".html", page)
            return parse_detail(page)
        details[url] = ctx.cached(url, load)
    return build_screenings(entries, details)


if __name__ == "__main__":  # manual check: python -m scrapers.sources.beacon
    context = Context(horizon_days=7)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
