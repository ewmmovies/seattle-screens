"""SIFF Cinema Uptown, SIFF Cinema Downtown and SIFF Film Center.

REFERENCE SCRAPER: every other source copies this layout.

  1. Constants: SOURCE_ID, VENUE_IDS, URLs.
  2. Pure parsing functions (text in, plain data out, no network). Tests call
     these against files saved in tests/fixtures/<source>/.
  3. Pure cleaning functions that turn parsed data into Screening records.
  4. fetch(ctx): the only function that touches the network. It raises on any
     problem; it never returns partial data quietly. The runner catches the
     error, keeps the last good data and marks the venues out of date.

Source: one server-rendered page per day covering all three venues,
https://www.siff.net/calendar?view=list&date=YYYY-MM-DD

Run by itself to see live output:  python -m scrapers.sources.siff
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from ..context import Context
from ..models import Screening, Showtime, merge_screenings
from ..util import clean_ws, epoch_ms_to_pacific, match_key, parse_time_12h

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "siff"
VENUE_IDS = ["siff-uptown", "siff-downtown", "siff-film-center"]

BASE_URL = "https://www.siff.net"
DAY_URL = BASE_URL + "/calendar?view=list&date={date}"

# The venue link beside each block of showtimes ends in one of these.
# (The embedded JSON says "SIFF Cinema Uptown House 2" etc., so the link is
# the reliable key.)
VENUE_BY_SLUG = {
    "siff-cinema-uptown": "siff-uptown",
    "siff-cinema-downtown": "siff-downtown",
    "siff-film-center": "siff-film-center",
}

# "Series: Title" is split when the ticketing name confirms it (see
# split_series). These lists are manual overrides for the cases it misses.
SERIES_PREFIXES = {
    "Romanian Film Festival Seattle",
    "PNW Awards",
    "Community Screening",
    "Nouvelles Femmes",
    "Holiday Favorites",
    "The Open Road",
    "Cinema Italian Style",
    "Movie Club",
    "Book Club",
}
NOT_SERIES_PREFIXES: set[str] = set()  # e.g. {"Mission"} if a real title gets split

STOP_AFTER_EMPTY_DAYS = 5

_FORMAT_RE = re.compile(r"\s*[\(\[]\s*(35|70|16)\s*mm\s*[\)\]]", re.IGNORECASE)
_DATE_FN_RE = re.compile(r"/Date\((-?\d+)\)/")
_HEADING_DATE_RE = re.compile(r"[A-Za-z]+,\s+([A-Za-z]+ \d{1,2}, \d{4})")


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing: HTML in, plain data out. No network, no cleaning decisions.
# --------------------------------------------------------------------------


@dataclass
class RawShow:
    venue_id: str
    time: str  # "HH:MM"
    event_name: str  # title as the ticketing system has it, without series prefix
    sold_out: bool


@dataclass
class RawItem:
    date: str
    title: str  # exactly as shown, e.g. "Nouvelles Femmes: My Night at Maud’s"
    url: str | None
    meta: str  # "France | 1969 | 105 min. | Éric Rohmer"
    notes: list[str] = field(default_factory=list)
    shows: list[RawShow] = field(default_factory=list)


def parse_heading_date(soup: BeautifulSoup) -> date | None:
    """The page prints the day it is showing, e.g. 'Tuesday, November 17, 2026'."""
    for span in soup.select(".h1 span, h1 span, h1"):
        match = _HEADING_DATE_RE.search(clean_ws(span.get_text()))
        if match:
            return datetime.strptime(match.group(1), "%B %d, %Y").date()
    return None


def parse_day(html: str, expected_date: date) -> list[RawItem]:
    """Parse one day's calendar page. Returns [] for a day with nothing on."""
    soup = BeautifulSoup(html, "html.parser")

    shown = parse_heading_date(soup)
    if shown is None:
        raise ParseError(f"{expected_date}: no date heading found; page layout may have changed")
    if shown != expected_date:
        raise ParseError(f"asked for {expected_date} but the page shows {shown}")

    items: list[RawItem] = []
    for node in soup.select("div.listing div.item"):
        title_link = node.select_one(".small-copy h3 a")
        if title_link is None:
            raise ParseError(f"{expected_date}: listing item without a title link")
        href = title_link.get("href")
        meta_node = node.select_one("p.meta")
        item = RawItem(
            date=expected_date.isoformat(),
            title=clean_ws(title_link.get_text()),
            url=(BASE_URL + href) if href and href.startswith("/") else href,
            meta=clean_ws(meta_node.get_text()) if meta_node else "",
            notes=[clean_ws(p.get_text()) for p in node.select("p.alert") if clean_ws(p.get_text())],
        )
        for block in node.select("div.times"):
            venue_link = block.select_one("h3 a")
            slug = (venue_link.get("href") or "").rstrip("/").rsplit("/", 1)[-1] if venue_link else ""
            venue_id = VENUE_BY_SLUG.get(slug)
            if venue_id is None:
                continue  # an off-site or festival venue we do not list
            for link in block.select("a[data-screening]"):
                item.shows.append(_parse_show(link, venue_id, expected_date))
        if item.shows:
            items.append(item)

    if soup.select("div.listing div.item") and not soup.select("a[data-screening]"):
        raise ParseError(f"{expected_date}: films listed but no showtime data; page layout may have changed")
    return items


def _parse_show(link, venue_id: str, expected_date: date) -> RawShow:
    try:
        data = json.loads(link["data-screening"])
    except (KeyError, ValueError) as error:
        raise ParseError(f"{expected_date}: unreadable showtime data") from error
    label = clean_ws(link.get_text())
    try:
        time = parse_time_12h(label)
    except ValueError:
        match = _DATE_FN_RE.search(str(data.get("Showtime", "")))
        if not match:
            raise ParseError(f"{expected_date}: showtime with no readable time ({label!r})")
        time = epoch_ms_to_pacific(int(match.group(1))).strftime("%H:%M")
    sold = data.get("PublicAllocationSoldOutPercentage")
    return RawShow(
        venue_id=venue_id,
        time=time,
        event_name=clean_ws(data.get("EventName") or ""),
        sold_out=isinstance(sold, (int, float)) and sold >= 100,
    )


# --------------------------------------------------------------------------
# 3. Cleaning: plain data in, Screening records out.
# --------------------------------------------------------------------------


def parse_meta(meta: str) -> tuple[int | None, int | None, list[str]]:
    """'USA | 2026 | 175 min. | A, B' -> (2026, 175, ['A', 'B']).

    Tolerates a missing director, a runtime without 'min.', and extra spaces.
    The first part is the country and is ignored.
    """
    parts = [clean_ws(part) for part in meta.split("|")]
    year = runtime = None
    leftover: list[str] = []
    for index, part in enumerate(parts):
        if not part:
            continue
        if year is None and re.fullmatch(r"(18|19|20)\d{2}", part):
            year = int(part)
        elif runtime is None and year is not None and re.fullmatch(r"(\d{1,3})(\s*min\.?)?", part, re.IGNORECASE):
            runtime = int(re.match(r"\d+", part).group())
        elif index > 0:
            leftover.append(part)
    directors = [clean_ws(name) for name in ", ".join(leftover).split(",") if clean_ws(name)]
    return year, runtime, directors


def split_format(title: str) -> tuple[str, str | None]:
    """'Paper Tiger (35mm)' -> ('Paper Tiger', '35mm')."""
    match = _FORMAT_RE.search(title)
    if not match:
        return title, None
    return clean_ws(_FORMAT_RE.sub("", title)), f"{match.group(1)}mm"


def split_series(title: str, event_name: str, repeated_prefixes: set[str]) -> tuple[str, str | None]:
    """'Nouvelles Femmes: My Night at Maud’s' -> ('My Night at Maud’s', 'Nouvelles Femmes').

    A colon alone is not enough ("Mission: Impossible"). The prefix counts as a
    series when any of these holds:
      - the ticketing system's own name for the event is just the part after
        the colon (the strongest signal, and it needs no upkeep);
      - the prefix is in SERIES_PREFIXES;
      - the same prefix is on two or more different titles in this run.
    """
    if ": " not in title:
        return title, None
    prefix, rest = (clean_ws(part) for part in title.split(": ", 1))
    if not prefix or not rest or prefix in NOT_SERIES_PREFIXES:
        return title, None
    confirmed = bool(event_name) and match_key(split_format(event_name)[0]) == match_key(rest)
    if confirmed or prefix in SERIES_PREFIXES or prefix in repeated_prefixes:
        return rest, prefix
    return title, None


def find_repeated_prefixes(items: list[RawItem]) -> set[str]:
    titles_by_prefix: dict[str, set[str]] = {}
    for item in items:
        if ": " in item.title:
            prefix = clean_ws(item.title.split(": ", 1)[0])
            titles_by_prefix.setdefault(prefix, set()).add(item.title)
    return {prefix for prefix, titles in titles_by_prefix.items() if len(titles) >= 2}


_TRAILING_YEAR_RE = re.compile(r"\s+(?:19|20)\d{2}$")


def unify_series_names(records: list[Screening]) -> None:
    """SIFF writes one series two ways ("Cinema Italian Style", "Cinema Italian Style 2026").
    When both are in a run, every record takes the name with the year."""
    with_year = {_TRAILING_YEAR_RE.sub("", r.series): r.series
                 for r in records if r.series and _TRAILING_YEAR_RE.search(r.series)}
    for record in records:
        if record.series in with_year:
            record.series = with_year[record.series]


def build_screenings(items: list[RawItem]) -> list[Screening]:
    """Turn every parsed item from the whole run into validated-shape records."""
    repeated = find_repeated_prefixes(items)
    records: list[Screening] = []
    for item in items:
        title, fmt = split_format(item.title)
        event_name = item.shows[0].event_name if item.shows else ""
        title, series = split_series(title, event_name, repeated)
        year, runtime, directors = parse_meta(item.meta)
        for venue_id in sorted({show.venue_id for show in item.shows}):
            shows = sorted(
                (show for show in item.shows if show.venue_id == venue_id),
                key=lambda show: show.time,
            )
            records.append(
                Screening(
                    venue_id=venue_id,
                    date=item.date,
                    title=title,
                    series=series,
                    directors=list(directors),
                    year=year,
                    runtime_min=runtime,
                    format=fmt,
                    notes=list(item.notes),
                    url=item.url,
                    # Tickets open in a pop-up on siff.net, so there is no
                    # direct link; the site falls back to `url`.
                    showtimes=[Showtime(time=show.time, sold_out=show.sold_out) for show in shows],
                )
            )
    unify_series_names(records)
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def fetch(ctx: Context) -> list[Screening]:
    items: list[RawItem] = []
    empty_run = 0
    for offset in range(ctx.horizon_days + 1):
        day = ctx.today + timedelta(days=offset)
        html = ctx.http.get_text(DAY_URL.format(date=day.isoformat()))
        if offset == 0:
            ctx.save_fixture(f"calendar_{day.isoformat()}.html", html)
        day_items = parse_day(html, day)
        items.extend(day_items)
        empty_run = 0 if day_items else empty_run + 1
        if empty_run >= STOP_AFTER_EMPTY_DAYS:
            break
    return build_screenings(items)


if __name__ == "__main__":  # manual check: python -m scrapers.sources.siff
    context = Context(horizon_days=3)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
