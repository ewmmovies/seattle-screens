"""The Beacon's past programs and past series, for the Past Programs page (added 2026-11-15).

- https://thebeacon.film/programs: the cards under "Past Programs", each with a month
  ("MAY 2026").
- https://thebeacon.film/series: the cards under "Past Series". Series carry no date,
  so this scraper notes the month each series is seen under Now Playing; once it moves
  to Past Series it takes the last month it was seen playing. Series that were already
  past before 2026-11-15 (Double Features) stay undated and sort to the end.

Past cards on the Beacon's listing pages have no pictures, so each item's own page is
read once for its picture (the Beacon's resized copy, with the original file as a
fallback) and the first sentence of its description. Past pages do not change, so
that is kept for good: only new arrivals are fetched. Images load from the Beacon's
servers and are never copied.

The archive is not capped (MAX_POSTS = None). The page shows only what the Beacon still
lists under Past Programs and Past Series. These items never appear in Latest News.
"""
from __future__ import annotations

import sys

import requests

from ..context import Context
from ..models import Post
from ..util import clean_ws, title_case_if_all_caps
from .beacon import (BASE_URL, MONTHS, PROGRAMS_URL, SERIES_URL, _MONTH_RE, _sections,
                     parse_detail)

SOURCE_ID = "beacon_past"
SOURCE_NAME = "The Beacon"
MAX_POSTS = None  # keep the whole archive

MONTH_NAMES = [None, "January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def parse_past_programs(html: str) -> list[Post]:
    posts = []
    for heading, cards in _sections(html, "programs"):
        if heading.lower() != "past programs":
            continue
        for card in cards:
            title = card.select_one(".card-title")
            meta = card.select_one(".card-meta")
            match = _MONTH_RE.match(clean_ws(meta.get_text()) if meta else "")
            if title is None or not match or match.group(1).lower() not in MONTHS:
                continue  # no readable month: skipped, as on the News page
            month, year = MONTHS[match.group(1).lower()], int(match.group(2))
            posts.append(_post(card, title, "Program", f"{year:04d}-{month:02d}-01"))
    return posts


def parse_series_sections(html: str) -> tuple[list[str], list[Post]]:
    """-> (URLs of series under Now Playing, Posts for series under Past Series, undated)."""
    playing, past = [], []
    for heading, cards in _sections(html, "series"):
        status = heading.lower()
        for card in cards:
            title = card.select_one(".card-title")
            if title is None:
                continue
            if status == "now playing":
                playing.append(BASE_URL + card["href"])
            elif status == "past series":
                past.append(_post(card, title, "Series", None))
    return playing, past


def _post(card, title, category: str, published: str | None) -> Post:
    return Post(
        source=SOURCE_ID,
        source_name=SOURCE_NAME,
        title=title_case_if_all_caps(clean_ws(title.get_text())),
        url=BASE_URL + card["href"],
        published=published,
        date_label=_label(published),
        category=category,
        happening=True,  # never in Latest News
        venue_label="The Beacon",
    )


def _label(published: str | None) -> str | None:
    return f"{MONTH_NAMES[int(published[5:7])]} {published[:4]}" if published else None


def fetch(ctx: Context) -> list[Post]:
    programs = parse_past_programs(ctx.http.get_text(PROGRAMS_URL))
    playing, series = parse_series_sections(ctx.http.get_text(SERIES_URL))

    # Remember the month each series is seen playing; a past series takes the last one.
    month = ctx.today.strftime("%Y-%m-01")
    for url in playing:
        ctx.cache["seen:" + url] = {"fetched": ctx.today.isoformat(), "data": month}
    for post in series:
        seen = (ctx.cache.get("seen:" + post.url) or {}).get("data")
        if seen:
            post.published, post.date_label = seen, _label(seen)

    for post in series + programs:
        key = "past:" + post.url
        detail = (ctx.cache.get(key) or {}).get("data")
        if detail is None:
            try:
                detail = parse_detail(ctx.http.get_text(post.url))
            except requests.HTTPError as error:  # this item goes without a picture; retried next run
                print(f"[posts/beacon_past] page skipped: {error}", file=sys.stderr)
                detail = None
            if detail is not None:  # kept for good: past pages do not change
                ctx.cache[key] = {"fetched": ctx.today.isoformat(), "data": {
                    k: detail.get(k) for k in ("first", "image", "image_fallback")}}
        detail = detail or {}
        first = detail.get("first") or ""
        post.description = first or None  # shown in full, held to two lines by the page
        post.summary = first if len(first) <= 240 else first[:237].rsplit(" ", 1)[0] + "…"
        post.image, post.image_fallback = detail.get("image"), detail.get("image_fallback")
    return series + programs
