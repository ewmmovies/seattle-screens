"""Build: merge the last-good data into the files the website reads.

    python -m scrapers.build

Reads data/sources/*.json (stale ones and regal.json included), data/posts/*.json
and data/status.json. Writes docs/data/screenings.json, posts.json and
status.json. Never fails because a file is missing (SPEC.md section 4.3).
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from .context import REPO_ROOT
from .run import KEEP_PAST_DAYS, read_json, write_json
from .util import now_pacific_iso, slugify, today_pacific

DATA_DIR = REPO_ROOT / "data"
SITE_DATA_DIR = REPO_ROOT / "docs" / "data"
MAX_POSTS = 60


def _load_files(folder: Path, key: str) -> list[dict]:
    records: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        try:
            records.extend(read_json(path, {}).get(key, []))
        except (json.JSONDecodeError, AttributeError) as error:
            print(f"Skipping unreadable {path.name}: {error}", file=sys.stderr)
    return records


def merge_by_id(records: list[dict]) -> list[dict]:
    """Same venue, date and title from two files: union the showtimes."""
    merged: dict[str, dict] = {}
    for record in records:
        rid = record.get("id") or f"{record['venue_id']}|{record['date']}|{slugify(record['title'])}"
        existing = merged.get(rid)
        if existing is None:
            merged[rid] = {**record, "id": rid}
            continue
        times = {show["time"] for show in existing["showtimes"]}
        existing["showtimes"] = sorted(
            existing["showtimes"] + [show for show in record["showtimes"] if show["time"] not in times],
            key=lambda show: show["time"],
        )
    return list(merged.values())


def build_screenings(records: list[dict], venue_order: list[str], today: date) -> dict:
    oldest = (today - timedelta(days=KEEP_PAST_DAYS)).isoformat()
    rank = {venue_id: index for index, venue_id in enumerate(venue_order)}
    kept = [r for r in merge_by_id(records) if r.get("date", "") >= oldest and r.get("showtimes")]
    kept.sort(key=lambda r: (r["date"], rank.get(r["venue_id"], len(rank)), r["showtimes"][0]["time"], r["title"]))
    dates = [r["date"] for r in kept]
    return {
        "generated_at": now_pacific_iso(),
        "range": {
            "start": min(dates) if dates else today.isoformat(),
            "end": max(dates) if dates else today.isoformat(),
        },
        "screenings": kept,
    }


POST_MONTHS = 6  # only posts released in the last six months are shown


def months_before(day: date, months: int) -> date:
    """Same day of the month, `months` earlier (clamped: Aug 31 -> Feb 28)."""
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    for last in (31, 30, 29, 28):
        try:
            return date(year, month, min(day.day, last))
        except ValueError:
            continue
    raise ValueError(day)


def build_posts(posts: list[dict], today: date) -> dict:
    """Posts released in the last six months, newest first. Undated posts are dropped,
    except series that are running now (current), which lead the feed."""
    cutoff = months_before(today, POST_MONTHS).isoformat()
    unique = {post["id"]: post for post in posts}.values()
    current = sorted((p for p in unique if p.get("current")), key=lambda p: p.get("title", ""))
    dated = [p for p in unique if not p.get("current") and (p.get("published") or "") >= cutoff]
    dated.sort(key=lambda p: (p["published"], p.get("title", "")), reverse=True)
    return {"generated_at": now_pacific_iso(), "posts": (current + dated)[:MAX_POSTS]}


HAPPENING_DAYS = 21  # "happening now" = a screening within the next three weeks


def series_key(text: str) -> str:
    """Loose key for matching a program's name to a screening's series:
    'SIFF Book Club' ~ 'Book Club', 'Community Screenings' ~ 'Community Screening'."""
    words = [w for w in slugify(text or "").split("-") if w and w not in {"siff", "the", "a", "an"}]
    return "-".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _names_match(a: str, b: str) -> bool:
    ka, kb = series_key(a), series_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    short, long_ = sorted((ka, kb), key=len)
    return short.count("-") >= 1 and long_.startswith(short + "-")  # two+ words: "cinema-italian-style" ~ "…-2026"


VENUE_PREFIX = {"SIFF": "siff-", "NWFF": "nwff"}


def next_screening(item: dict, screenings: list[dict], today: date) -> str | None:
    """Next date (within HAPPENING_DAYS) of a screening at this item's theater whose series matches."""
    prefix = VENUE_PREFIX.get(item.get("venue_label") or "")
    if not prefix:
        return None
    first, last = today.isoformat(), (today + timedelta(days=HAPPENING_DAYS)).isoformat()
    dates = [s["date"] for s in screenings
             if s.get("venue_id", "").startswith(prefix) and s.get("series")
             and first <= s.get("date", "") <= last and _names_match(item["title"], s["series"])]
    return min(dates) if dates else None


def _short_date(iso: str) -> str:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{months[int(iso[5:7]) - 1]} {int(iso[8:10])}"


def _card(post: dict, when: str) -> dict:
    return {
        "title": post["title"],
        "url": post["url"],
        "venue": post.get("venue_label") or post.get("source_name") or "",
        "kind": post.get("category") or "",
        "when": when,
        "byline": post.get("byline") or "",
        "description": post.get("description") or "",
        "months": post.get("months") or "",
        "image": post.get("image"),
        "image_fallback": post.get("image_fallback"),
    }


def build_features(posts: list[dict], screenings: list[dict], today: date) -> dict:
    """Happening Now (SPEC addition 2026-11-15).

    lead: the Beacon's current series (arrows rotate through them), or its now-playing
          programs if it has no series.
    row:  SIFF programs/events and NWFF festivals/series with a matching screening in the
          next three weeks, plus Beacon now-playing programs; theaters alternate.
    """
    unique = list({post["id"]: post for post in posts}.values())
    today_s = today.isoformat()

    def beacon_when(p: dict) -> str:
        if p.get("category") == "Program" and p.get("date_label"):
            return p["date_label"]
        nxt = p.get("next_date")
        return f"Next: {_short_date(nxt)}" if nxt and nxt >= today_s else "Now playing"

    beacon_now = [p for p in unique if p.get("source") == "beacon" and p.get("now_playing")]
    series = sorted((p for p in beacon_now if p.get("category") == "Series"), key=lambda p: p["title"])
    programs = sorted((p for p in beacon_now if p.get("category") == "Program"), key=lambda p: p["title"])

    if series:
        lead = [_card(p, "Now playing") for p in series]
        row_beacon = programs
    else:
        lead = [_card(p, beacon_when(p)) for p in programs[:1]]
        row_beacon = programs[1:]

    def pool(source: str) -> list[dict]:
        found = []
        for p in unique:
            if p.get("source") != source or not p.get("listed", True):
                continue
            nxt = next_screening(p, screenings, today)
            if nxt:
                found.append((nxt, p["title"], _card(p, f"Next: {_short_date(nxt)}")))
        return [card for _, _, card in sorted(found, key=lambda t: (t[0], t[1]))]

    queues = [pool("siff_programs"), pool("nwff_programs"),
              [_card(p, beacon_when(p)) for p in row_beacon]]
    row: list[dict] = []
    while any(queues):  # alternate theaters: SIFF, NWFF, Beacon, SIFF, …
        for queue in queues:
            if queue:
                row.append(queue.pop(0))
    if not lead and row:  # nothing from the Beacon at all: the first row item moves up
        lead, row = [row[0]], row[1:]
    return {"generated_at": now_pacific_iso(), "lead": lead, "row": row}


def build(data_dir: Path = DATA_DIR, site_data_dir: Path = SITE_DATA_DIR, today: date | None = None) -> None:
    today = today or today_pacific()
    venues = read_json(site_data_dir / "venues.json", [])
    screenings = build_screenings(_load_files(data_dir / "sources", "screenings"), [v["id"] for v in venues], today)
    all_posts = _load_files(data_dir / "posts", "posts")
    posts = build_posts([p for p in all_posts if not p.get("happening")], today)
    features = build_features(all_posts, screenings["screenings"], today)
    status = read_json(data_dir / "status.json", {})
    status.setdefault("sources", {})
    status.setdefault("posts", {})
    status["generated_at"] = now_pacific_iso()

    write_json(site_data_dir / "screenings.json", screenings)
    write_json(site_data_dir / "posts.json", posts)
    write_json(site_data_dir / "features.json", features)
    write_json(site_data_dir / "status.json", status)
    print(
        f"Built {len(screenings['screenings'])} screenings "
        f"({screenings['range']['start']} to {screenings['range']['end']}) and {len(posts['posts'])} posts."
    )


if __name__ == "__main__":
    build()
