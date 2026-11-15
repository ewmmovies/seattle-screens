"""Northwest Film Forum (Capitol Hill).

Same layout as siff.py: constants, pure parsing, cleaning, then fetch().

Source: weekly calendar pages, https://nwfilmforum.org/calendar/?start=YYYY-MM-DD.
Each entry (div.calendar__item) carries schema.org microdata: start time, name,
duration and the film page. The class says what it is: --film, --event or
--workshop (workshops are skipped). The scraper starts at today's date and
follows the page's own "Next Week" link, so it does not depend on which day
NWFF's week starts (observed: Friday).

Film pages (cached for a week) give director, year, runtime, a "Series - Name"
line and the Eventive ticket link.

Run by itself to see live output:  python -m scrapers.sources.nwff
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
from ..util import clean_ws, match_key, parse_hm_minutes, parse_iso_duration_minutes, title_case_if_all_caps

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "nwff"
VENUE_IDS = ["nwff"]

BASE_URL = "https://nwfilmforum.org"
WEEK_URL = BASE_URL + "/calendar/?start={date}"
MAX_WEEKS = 6

KINDS = {"film": "film", "event": "event"}  # calendar__item--<type>; anything else is skipped

# Calendar attribute icons (icon-<name>). "On Film" sets the format; the rest become notes.
ATTRIBUTE_NOTES = {
    "visiting_artist": "Visiting artist",
    "live_music": "Live music",
    "discussion": "Discussion",
}

_RESTORATION_RE = re.compile(r"\s*\((\d+K Restoration|Restoration|New Restoration)\)\s*$", re.IGNORECASE)
_GAUGE_RE = re.compile(r"\b(35|70|16)\s*mm\b", re.IGNORECASE)


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing
# --------------------------------------------------------------------------


@dataclass
class RawItem:
    kind: str  # "film" or "event"
    start: datetime  # local Seattle time, as the page gives it
    name: str
    url: str | None
    duration_min: int | None
    attributes: list[str] = field(default_factory=list)  # e.g. ["on_film", "visiting_artist"]


def parse_week(html: str) -> tuple[list[RawItem], str | None]:
    """One calendar page -> (items, start date of the next week or None)."""
    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select("div.calendar__item")
    if not nodes and soup.select_one(".calendar__day-list, .calendar__grid") is None:
        raise ParseError("no calendar found on the page; layout may have changed")
    items: list[RawItem] = []
    for node in nodes:
        kind = next((KINDS[c.split("--", 1)[1]] for c in node.get("class", [])
                     if c.startswith("calendar__item--") and c.split("--", 1)[1] in KINDS), None)
        if kind is None:
            continue  # workshops and anything new
        start_meta = node.select_one('meta[itemprop="startDate"]')
        name_meta = node.select_one('meta[itemprop="name"]')
        if start_meta is None or name_meta is None:
            raise ParseError("calendar item without a start date or name")
        try:
            start = datetime.fromisoformat(start_meta["content"])
        except (KeyError, ValueError) as error:
            raise ParseError(f"unreadable start date {start_meta.get('content')!r}") from error
        page = node.select_one('meta[itemprop="mainEntityOfPage"]') or node.select_one('meta[itemprop="url"]')
        link = node.select_one("a.calendar__item__link")
        url = (page.get("content") if page else None) or (link.get("href") if link else None)
        duration = node.select_one('meta[itemprop="duration"]')
        attributes = []
        for icon in node.select(".calendar-popup__attributes [class*='icon-']"):
            for cls in icon.get("class", []):
                if cls.startswith("icon-"):
                    attributes.append(cls[5:])
        items.append(RawItem(
            kind=kind,
            start=start,
            name=clean_ws(name_meta.get("content")),
            url=url,
            duration_min=parse_iso_duration_minutes(duration.get("content")) if duration else None,
            attributes=attributes,
        ))
    next_link = next((a for a in soup.find_all("a", href=True)
                      if "start=" in a["href"] and "next" in a.get_text().lower()), None)
    next_start = None
    if next_link:
        match = re.search(r"start=(\d{4}-\d{2}-\d{2})", next_link["href"])
        next_start = match.group(1) if match else None
    return items, next_start


def parse_detail(html: str) -> dict:
    """Film or event page -> directors, year, runtime, series, ticket link, gauge."""
    soup = BeautifulSoup(html, "html.parser")
    credits = [clean_ws(n.get_text()) for n in soup.select(".film-details .film-details__item")]
    year = runtime = None
    directors: list[str] = []
    for index, item in enumerate(credits):
        if year is None and re.fullmatch(r"(18|19|20)\d{2}", item):
            year = int(item)
        elif runtime is None and parse_hm_minutes(item) is not None:
            runtime = parse_hm_minutes(item)
    # Credits run director, country, year, runtime. Only trust the first item as the
    # director when it is not itself the year or the runtime.
    if credits and not re.fullmatch(r"\d{4}", credits[0]) and parse_hm_minutes(credits[0]) is None and len(credits) >= 3:
        directors = [n for n in re.split(r",\s*|\s+&\s+|\s+and\s+", credits[0]) if n]

    # Fallback: the About section opens with "(John Cassavetes, 1984, United States, 140 min, in English)".
    about = soup.select_one('[itemprop="about"] p')
    if about:
        match = re.match(r"^\((.+)\)$", clean_ws(about.get_text()))
        if match:
            parts = [p.strip() for p in match.group(1).split(",")]
            year_index = next((i for i, p in enumerate(parts) if re.fullmatch(r"(18|19|20)\d{2}", p)), None)
            if year_index is not None:
                if year is None:
                    year = int(parts[year_index])
                if not directors and year_index > 0:
                    directors = parts[:year_index]
            if runtime is None:
                runtime = next((parse_hm_minutes(p) for p in parts if parse_hm_minutes(p)), None)

    series = None
    for node in soup.select("div.font-size-small"):
        text = clean_ws(node.get_text())
        if text.startswith("Series -") or text.startswith("Series:"):
            series = clean_ws(re.sub(r"^Series\s*[-:]\s*", "", text)) or None
            break

    tickets = soup.select_one('a[href*="eventive.org"]')
    gauge = None
    details_text = " ".join(credits)
    match = _GAUGE_RE.search(details_text)
    if match:
        gauge = f"{match.group(1)}mm"
    return {
        "directors": directors,
        "year": year,
        "runtime_min": runtime,
        "series": series,
        "ticket_url": tickets["href"] if tickets else None,
        "format": gauge,
    }


# --------------------------------------------------------------------------
# 3. Cleaning
# --------------------------------------------------------------------------


def clean_title(name: str, series: str | None) -> tuple[str, list[str]]:
    """'Unstreamable - Love Streams' (series Unstreamable) -> 'Love Streams';
    'Go Fish (4K Restoration)' -> 'Go Fish' plus a note."""
    title = name
    notes: list[str] = []
    if series:
        for sep in (" - ", ": ", " – "):
            if sep in title:
                prefix, rest = title.split(sep, 1)
                if match_key(prefix) == match_key(series) and rest.strip():
                    title = rest.strip()
                    break
    match = _RESTORATION_RE.search(title)
    if match:
        notes.append(re.sub(r"Restoration", "restoration", match.group(1)))  # "4K restoration"
        title = _RESTORATION_RE.sub("", title).strip()
    return title_case_if_all_caps(title), notes


def build_screenings(items: list[RawItem], details: dict[str, dict]) -> list[Screening]:
    # Attributes shared by every showing of a title on a day are record notes;
    # ones that only some showings have become showtime notes.
    groups: dict[tuple[str, str], list[RawItem]] = {}
    for item in items:
        groups.setdefault((item.start.date().isoformat(), item.url or item.name), []).append(item)

    records = []
    for (day, _), group in groups.items():
        first = group[0]
        info = details.get(first.url or "") or {}
        title, notes = clean_title(first.name, info.get("series"))
        attribute_sets = [set(i.attributes) for i in group]
        shared = set.intersection(*attribute_sets)
        fmt = "Film" if "on_film" in shared else None
        fmt = info.get("format") or fmt
        for attr in sorted(shared):
            if attr in ATTRIBUTE_NOTES:
                notes.append(ATTRIBUTE_NOTES[attr])
        showtimes = []
        for item in sorted(group, key=lambda i: i.start):
            own = [ATTRIBUTE_NOTES[a] for a in item.attributes if a not in shared and a in ATTRIBUTE_NOTES]
            if "on_film" in item.attributes and "on_film" not in shared:
                own.insert(0, "On film")
            showtimes.append(Showtime(
                time=item.start.strftime("%H:%M"),
                ticket_url=info.get("ticket_url"),
                note="; ".join(own) or None,
            ))
        records.append(Screening(
            venue_id="nwff",
            date=day,
            title=title,
            kind=first.kind,
            series=info.get("series"),
            directors=list(info.get("directors") or []),
            year=info.get("year"),
            runtime_min=info.get("runtime_min") or first.duration_min,
            format=fmt,
            notes=notes,
            url=first.url,
            showtimes=showtimes,
        ))
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def fetch(ctx: Context) -> list[Screening]:
    first_day = ctx.today.isoformat()
    last_day = (ctx.today + timedelta(days=ctx.horizon_days)).isoformat()
    items: list[RawItem] = []
    start = first_day
    for week in range(MAX_WEEKS):
        html = ctx.http.get_text(WEEK_URL.format(date=start))
        if week == 0:
            ctx.save_fixture(f"calendar_{start}.html", html)
        week_items, next_start = parse_week(html)
        items.extend(i for i in week_items if first_day <= i.start.date().isoformat() <= last_day)
        if not next_start or next_start > last_day or next_start <= start:
            break
        start = next_start

    details: dict[str, dict] = {}
    for url in sorted({i.url for i in items if i.url}):
        def load(url=url):
            try:
                page = ctx.http.get_text(url)
            except requests.HTTPError as error:  # one missing film page should not sink the venue
                print(f"[nwff] detail page skipped: {error}", file=sys.stderr)
                return {}
            if not details:
                ctx.save_fixture("film_" + url.rstrip("/").rsplit("/", 1)[-1] + ".html", page)
            return parse_detail(page)
        details[url] = ctx.cached(url, load)
    return build_screenings(items, details)


if __name__ == "__main__":  # manual check: python -m scrapers.sources.nwff
    context = Context(horizon_days=7)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
