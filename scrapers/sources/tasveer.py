"""Tasveer Film Center (Columbia City).

Same layout as siff.py: constants, pure parsing, cleaning, then fetch().

Source: the site's GraphQL endpoint (INDY Cinema Group platform),
https://filmcenter.tasveer.org/graphql. It answers only when the request
carries the same site headers the website sends (site 262, circuit 138,
client type "consumer"); found in the browser on 2026-11-15.
  - datesWithShowing: the dates that have showings (about six days ahead).
  - showingsForDate(date): that day's showings. Times are UTC; the record date
    is the Pacific date.
The queries below ask only for the fields used.

Run by itself to see live output:  python -m scrapers.sources.tasveer
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from ..context import Context
from ..models import Screening, Showtime, merge_screenings
from ..util import PACIFIC, clean_ws, title_case_if_all_caps

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "tasveer"
VENUE_IDS = ["tasveer"]

BASE_URL = "https://filmcenter.tasveer.org"
GRAPHQL_URL = BASE_URL + "/graphql"
SITE_ID = "262"
HEADERS = {
    "content-type": "application/json",
    "accept": "application/json",
    "site-id": SITE_ID,
    "circuit-id": "138",
    "client-type": "consumer",
}

DATES_QUERY = "query ($siteIds: [ID]) { datesWithShowing(siteIds: $siteIds) { value } }"
SHOWINGS_QUERY = (
    "query ($date: String, $siteIds: [ID]) { showingsForDate(date: $date, siteIds: $siteIds) "
    "{ data { id time published private displayMetaData "
    "movie { id name urlSlug directedBy duration releaseDate } } } }"
)

# Showing badges (CSS classes in displayMetaData) worth showing as notes.
# Building-access badges (wheelchair, stairs) are about the room, not the screening: ignored.
BADGE_NOTES = [
    (re.compile(r"^open-captions?$"), "Open captions"),
    (re.compile(r"^subtitled"), "English subtitles"),
]

# "La Bola Negra (2026, Spain, Spanish)" -> trailing year/country/language parenthetical.
_TRAILING_INFO_RE = re.compile(r"\s*\((?=[^()]*\b(?:1[89]\d{2}|20\d{2})\b|[^()]*,)[^()]*\)\s*$")
_QA_RE = re.compile(r"\s*[-–—:]?\s*(?:\(|\b)(with\s+(?:a\s+)?(?:post|pre)[- ]film\s+(?:q\s*&\s*a|discussion|conversation)[^)]*)\)?\s*$",
                    re.IGNORECASE)


class ParseError(RuntimeError):
    """The response did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing
# --------------------------------------------------------------------------


def _data(response: dict, field: str):
    if not isinstance(response, dict):
        raise ParseError("response is not JSON object")
    if response.get("errors") or response.get("error"):
        problem = (response.get("errors") or [response.get("error")])[0]
        message = problem.get("message") if isinstance(problem, dict) else problem
        raise ParseError(f"GraphQL error: {message}")
    try:
        return response["data"][field]
    except (KeyError, TypeError) as error:
        raise ParseError(f"response has no {field}") from error


def parse_dates(response: dict) -> list[str]:
    value = (_data(response, "datesWithShowing") or {}).get("value")
    try:
        dates = json.loads(value) if isinstance(value, str) else value
    except ValueError as error:
        raise ParseError("datesWithShowing value is not a JSON list") from error
    if not isinstance(dates, list):
        raise ParseError("datesWithShowing value is not a list")
    return [d for d in dates if isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)]


def parse_showings(response: dict) -> list[dict]:
    showings = (_data(response, "showingsForDate") or {}).get("data")
    if not isinstance(showings, list):
        raise ParseError("showingsForDate has no data list")
    return showings


def showing_badges(showing: dict) -> list[str]:
    try:
        meta = json.loads(showing.get("displayMetaData") or "{}")
    except ValueError:
        return []
    return (meta.get("classes") or "").split() if isinstance(meta, dict) else []


# --------------------------------------------------------------------------
# 3. Cleaning
# --------------------------------------------------------------------------


def clean_title(name: str) -> tuple[str, list[str]]:
    """'La Bola Negra (2026, Spain, Spanish)' -> 'La Bola Negra'; Q&A text -> a note."""
    title = clean_ws(name)
    notes = []
    match = _QA_RE.search(title)
    if match:
        note = match.group(1).strip()
        notes.append(note[0].upper() + note[1:])
        title = title[: match.start()].strip()
    title = _TRAILING_INFO_RE.sub("", title).strip()
    return title_case_if_all_caps(title), notes


def build_screenings(showings: list[dict]) -> list[Screening]:
    records = []
    for showing in showings:
        if not showing.get("published") or showing.get("private"):
            continue
        movie = showing.get("movie") or {}
        if not movie.get("name"):
            raise ParseError(f"showing {showing.get('id')} has no film name")
        try:
            start = datetime.fromisoformat(str(showing["time"]).replace("Z", "+00:00"))
        except (KeyError, ValueError) as error:
            raise ParseError(f"unreadable time on showing {showing.get('id')}") from error
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        local = start.astimezone(PACIFIC)

        title, notes = clean_title(movie["name"])
        badges = showing_badges(showing)
        badge_notes = [label for pattern, label in BADGE_NOTES if any(pattern.search(b) for b in badges)]
        year = re.match(r"(18|19|20)\d{2}", str(movie.get("releaseDate") or ""))
        duration = movie.get("duration")
        slug = movie.get("urlSlug")
        records.append(Screening(
            venue_id="tasveer",
            date=local.date().isoformat(),
            title=title,
            directors=[d.strip() for d in str(movie.get("directedBy") or "").split(",") if d.strip()],
            year=int(year.group()) if year else None,
            runtime_min=duration if isinstance(duration, int) and duration > 0 else None,
            notes=notes,
            url=f"{BASE_URL}/movie/{slug}/" if slug else f"{BASE_URL}/showtimes/",
            showtimes=[Showtime(time=local.strftime("%H:%M"), note="; ".join(badge_notes) or None)],
        ))
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def _post(ctx: Context, query: str, variables: dict, fixture: str | None = None) -> dict:
    text = ctx.http.post_text(GRAPHQL_URL, data=json.dumps({"query": query, "variables": variables}), headers=HEADERS)
    if fixture:
        ctx.save_fixture(fixture, text)
    try:
        return json.loads(text)
    except ValueError as error:
        raise ParseError("GraphQL response is not JSON") from error


def fetch(ctx: Context) -> list[Screening]:
    first = ctx.today.isoformat()
    last = (ctx.today + timedelta(days=ctx.horizon_days)).isoformat()
    dates = [d for d in parse_dates(_post(ctx, DATES_QUERY, {"siteIds": [SITE_ID]}, "dates.json")) if first <= d <= last]
    showings: list[dict] = []
    for index, day in enumerate(sorted(dates)):
        response = _post(ctx, SHOWINGS_QUERY, {"date": day, "siteIds": [SITE_ID]},
                         f"showings_{day}.json" if index == 0 else None)
        showings.extend(parse_showings(response))
    records = build_screenings(showings)
    return [r for r in records if first <= r.date <= last]


if __name__ == "__main__":  # manual check: python -m scrapers.sources.tasveer
    context = Context(horizon_days=21)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
