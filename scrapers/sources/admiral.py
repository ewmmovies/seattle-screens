"""Historic Admiral Theater (West Seattle).

Same layout as siff.py: constants, pure parsing, cleaning, then fetch().

Source: the Mobile Moviegoing API behind farawayentertainment.com.
POST getShowtimesByDayDisplay.php with a JSON string body (sent without a JSON
content-type, as the site does): {"eid", "pos_route", "date": "YYYYMMDD",
"mode": "now", "location": "00001-00001-00002"}. "eid" is a site key read
from the home page at run time.

The response's validDates says which dates have shows; one request per date.
Each film carries its screenings. Their startTime is a Unix timestamp of the
*local* wall-clock time ("localized": true): 1794744900 is 12:15 PM in Seattle
on 2026-11-15, not 4:15 AM. Checked against the live page on 2026-11-15.

The page's "** DISCOUNTED PRICING **" label is worked out in the browser and is
not in the data, so it is not shown.

Run by itself to see live output:  python -m scrapers.sources.admiral
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone

from ..context import Context
from ..models import Screening, Showtime, merge_screenings
from ..util import clean_ws, title_case_if_all_caps

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------

SOURCE_ID = "admiral"
VENUE_IDS = ["admiral"]

SITE_URL = "https://www.farawayentertainment.com/"
API_URL = "https://api-v3.mobilemoviegoing.cloud/include/app/getShowtimesByDayDisplay.php"
LOCATION = "00001-00001-00002"  # the Admiral
FALLBACK_EID = "efbc509c-5e9b-4178-8dc6-a2e635ba8057"

_EID_RE = re.compile(r"\beid\s*[:=]\s*[\"']([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})[\"']", re.IGNORECASE)

# Screening attributes worth showing, matched on their title. Hearing-assistance
# devices are available at every show and are not repeated on each one.
ATTRIBUTE_NOTES = [
    (re.compile(r"open\s*caption", re.IGNORECASE), "Open captions"),
    (re.compile(r"discount", re.IGNORECASE), "Discount pricing"),
]


class ParseError(RuntimeError):
    """The response did not look the way this scraper expects."""


# --------------------------------------------------------------------------
# 2. Parsing
# --------------------------------------------------------------------------


def find_eid(html: str) -> str | None:
    match = _EID_RE.search(html or "")
    return match.group(1) if match else None


def parse_day(data) -> tuple[list[dict], list[str]]:
    """Response -> (films, dates with shows as YYYY-MM-DD)."""
    if not isinstance(data, dict):
        raise ParseError("response is not a JSON object")
    if data.get("error"):
        raise ParseError(f"API error: {data.get('error_message') or data.get('error')}")
    films = data.get("films")
    if not isinstance(films, list):
        raise ParseError("response has no films list")
    valid = data.get("validDates") or {}
    dates = sorted(f"{d[:4]}-{d[4:6]}-{d[6:]}" for d, on in valid.items()
                   if on and isinstance(d, str) and re.fullmatch(r"\d{8}", d))
    return films, dates


def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def local_start(screening: dict) -> datetime:
    """Wall-clock Seattle time from the 'localized' timestamp."""
    raw = screening.get("startTime", screening.get("startTimeUtc"))
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError) as error:
        raise ParseError(f"unreadable startTime {raw!r}") from error


# --------------------------------------------------------------------------
# 3. Cleaning
# --------------------------------------------------------------------------


def build_screenings(films: list[dict]) -> list[Screening]:
    records = []
    for film in films:
        name = clean_ws(film.get("dispName"))
        if not name:
            raise ParseError(f"film {film.get('id')} has no name")
        release = re.match(r"(18|19|20)\d{2}", str(film.get("ReleaseDate") or ""))
        try:
            seconds = int(film.get("Runtime") or 0)
        except ValueError:
            seconds = 0
        for screening in film.get("screenings") or []:
            if not screening.get("display", 1) or not screening.get("enabled", 1):
                continue
            start = local_start(screening)
            titles = " ".join(str(a.get("title") or "") + " " + str(a.get("POSName") or "") + " " + str(a.get("attrib") or "")
                              for a in screening.get("attributes") or [] if isinstance(a, dict))
            notes = [label for pattern, label in ATTRIBUTE_NOTES if pattern.search(titles)]
            records.append(Screening(
                venue_id="admiral",
                date=start.date().isoformat(),
                title=title_case_if_all_caps(name),
                directors=[clean_ws(d) for d in _json_list(film.get("Director")) if clean_ws(str(d))],
                year=int(release.group()) if release else None,
                runtime_min=round(seconds / 60) if seconds > 0 else None,
                url=SITE_URL,
                showtimes=[Showtime(
                    time=start.strftime("%H:%M"),
                    ticket_url=SITE_URL,
                    note="; ".join(notes) or None,
                    sold_out=bool(screening.get("isSoldOut")),
                )],
            ))
    return merge_screenings(records)


# --------------------------------------------------------------------------
# 4. Network
# --------------------------------------------------------------------------


def _request_day(ctx: Context, eid: str, day: str, fixture: str | None = None):
    body = json.dumps({"eid": eid, "pos_route": 1, "date": day.replace("-", ""), "mode": "now", "location": LOCATION})
    text = ctx.http.post_text(API_URL, data=body)
    if fixture:
        ctx.save_fixture(fixture, text)
    try:
        return json.loads(text)
    except ValueError as error:
        raise ParseError("API response is not JSON") from error


def fetch(ctx: Context) -> list[Screening]:
    try:
        eid = find_eid(ctx.http.get_text(SITE_URL)) or FALLBACK_EID
    except Exception as error:  # noqa: BLE001 - the known key still works
        print(f"[admiral] home page unavailable, using the saved site key: {error}", file=sys.stderr)
        eid = FALLBACK_EID

    first = ctx.today.isoformat()
    last = (ctx.today + timedelta(days=ctx.horizon_days)).isoformat()
    films, dates = parse_day(_request_day(ctx, eid, first, f"showtimes_{first.replace('-', '')}.json"))
    records = build_screenings(films)
    for day in dates:
        if first < day <= last:
            day_films, _ = parse_day(_request_day(ctx, eid, day))
            records.extend(build_screenings(day_films))
    return [r for r in merge_screenings(records) if first <= r.date <= last]


if __name__ == "__main__":  # manual check: python -m scrapers.sources.admiral
    context = Context(horizon_days=7)
    result = fetch(context)
    for record in result:
        record.validate(set(VENUE_IDS))
    print(json.dumps([record.to_dict() for record in result], indent=2, ensure_ascii=False))
    print(f"\n{len(result)} screenings, {context.http.request_count} requests")
