"""Majestic Bay Theatre (Ballard).

Same layout as siff.py: constants, pure parsing, cleaning, then fetch().

Source: the JSON API behind majesticbay.com (BoxOffice platform), theater X05TV.
  - schedule?from=…&to=…&theaters={"id":"X05TV",…}: every showtime in the range,
    keyed by movie id, then by the date the theater lists it under.
  - movies?ids=…: title, runtime (seconds), directors and release date.
One schedule request covers the whole horizon (checked live 2026-11-14), so a
full run is two requests.

Run by itself to see live output:  python -m scrapers.sources.majestic_bay
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote

from ..context import Context
from ..models import Screening, Showtime, merge_screenings
from ..util import clean_ws, title_case_if_all_caps

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "majestic_bay"
VENUE_IDS = ["majestic-bay"]

THEATER_ID = "X05TV"
SITE_URL = "https://www.majesticbay.com/"
API = "https://www.majesticbay.com/api/gatsby-source-boxofficeapi/"
THEATERS_PARAM = quote(json.dumps({"id": THEATER_ID, "timeZone": "America/Los_Angeles"}, separators=(",", ":")))
# Business days run 3 AM to 3 AM, so a 12:30 AM show stays on the evening it belongs to.
SCHEDULE_URL = API + "schedule?from={start}T03:00:00&to={end}T03:00:00&theaters=" + THEATERS_PARAM
MOVIES_URL = API + "movies?basic=false&castingLimit=3&{ids}"

FORMAT_TAGS = {
    "Format.Projection.Digital": "Digital",
    "Format.Projection.35mm": "35mm",
    "Format.Projection.70mm": "70mm",
    "Format.Projection.16mm": "16mm",
}


class ParseError(RuntimeError):
    """The response did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing
# --------------------------------------------------------------------------


def parse_schedule(data) -> dict[str, dict[str, list[dict]]]:
    """Response -> {movie_id: {date: [showtime, …]}}."""
    if not isinstance(data, dict) or THEATER_ID not in data or "schedule" not in (data[THEATER_ID] or {}):
        raise ParseError("schedule response has no X05TV schedule; the API may have changed")
    schedule = data[THEATER_ID]["schedule"] or {}
    if not isinstance(schedule, dict):
        raise ParseError("schedule is not a mapping")
    return schedule


def parse_movies(data) -> dict[str, dict]:
    """Response (a list, or a mapping by id) -> {movie_id: {title, directors, year, runtime_min}}."""
    items = data if isinstance(data, list) else list((data or {}).values())
    movies = {}
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            continue
        release = re.match(r"(18|19|20)\d{2}", str(item.get("release") or ""))
        runtime = item.get("runtime")
        movies[str(item["id"])] = {
            "title": clean_ws(item.get("title")),
            "directors": [clean_ws(d) for d in item.get("direction") or [] if clean_ws(d)],
            "year": int(release.group()) if release else None,
            "runtime_min": round(runtime / 60) if isinstance(runtime, (int, float)) and runtime > 0 else None,
        }
    return movies


def _ticket_url(show: dict) -> str | None:
    for entry in (show.get("data") or {}).get("ticketing") or []:
        if entry.get("provider") == "default" and entry.get("urls"):
            return entry["urls"][0]
    return None


def _format(tags: list[str]) -> str | None:
    for tag in tags:
        if tag in FORMAT_TAGS:
            return FORMAT_TAGS[tag]
    return None  # unknown projection tags: never guess


# --------------------------------------------------------------------------
# 3. Cleaning
# --------------------------------------------------------------------------


def build_screenings(schedule: dict, movies: dict[str, dict]) -> list[Screening]:
    records = []
    for movie_id, days in schedule.items():
        movie = movies.get(str(movie_id))
        if not movie or not movie["title"]:
            raise ParseError(f"no film details for movie id {movie_id}")
        for day, shows in days.items():
            showtimes = []
            formats = set()
            for show in shows:
                try:
                    start = datetime.fromisoformat(show["startsAt"])
                except (KeyError, ValueError) as error:
                    raise ParseError(f"unreadable startsAt in {show!r}") from error
                showtimes.append(Showtime(time=start.strftime("%H:%M"), ticket_url=_ticket_url(show)))
                formats.add(_format(show.get("tags") or []))
            showtimes.sort(key=lambda s: s.time)
            records.append(Screening(
                venue_id="majestic-bay",
                date=day,
                title=title_case_if_all_caps(movie["title"]),
                directors=list(movie["directors"]),
                year=movie["year"],
                runtime_min=movie["runtime_min"],
                format=formats.pop() if len(formats) == 1 else None,
                url=SITE_URL,
                showtimes=showtimes,
            ))
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def fetch(ctx: Context) -> list[Screening]:
    start = ctx.today.isoformat()
    end = (ctx.today + timedelta(days=ctx.horizon_days + 1)).isoformat()
    text = ctx.http.get_text(SCHEDULE_URL.format(start=start, end=end))
    ctx.save_fixture("schedule.json", text)
    schedule = parse_schedule(json.loads(text))
    schedule = {mid: {d: s for d, s in days.items() if start <= d < end} for mid, days in schedule.items()}
    schedule = {mid: days for mid, days in schedule.items() if days}
    if not schedule:
        return []
    ids = "&".join(f"ids={quote(str(mid))}" for mid in sorted(schedule))
    movies_text = ctx.http.get_text(MOVIES_URL.format(ids=ids))
    ctx.save_fixture("movies.json", movies_text)
    return build_screenings(schedule, parse_movies(json.loads(movies_text)))


if __name__ == "__main__":  # manual check: python -m scrapers.sources.majestic_bay
    context = Context(horizon_days=7)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
