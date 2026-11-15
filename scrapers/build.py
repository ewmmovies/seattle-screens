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


MAX_FEATURES = 4


def build_features(posts: list[dict]) -> dict:
    """Up to four Beacon series and programs now playing; series first (SPEC addition 2026-11-15)."""
    unique = {post["id"]: post for post in posts}.values()
    now = [p for p in unique if p.get("source") == "beacon" and p.get("now_playing")]
    series = sorted((p for p in now if p.get("category") == "Series"), key=lambda p: p.get("title", ""))
    programs = sorted((p for p in now if p.get("category") == "Program"), key=lambda p: p.get("title", ""))
    programs.sort(key=lambda p: p.get("published") or "", reverse=True)  # newest month first, then A-Z
    features = [{
        "title": p["title"],
        "url": p["url"],
        "kind": p.get("category"),
        "when": p.get("date_label") or "",
        "byline": p.get("byline") or "",
        "description": p.get("description") or "",
        "months": p.get("months") or "",
        "image": p.get("image"),
        "image_fallback": p.get("image_fallback"),
    } for p in (series + programs)[:MAX_FEATURES]]
    return {"generated_at": now_pacific_iso(), "features": features}


def build(data_dir: Path = DATA_DIR, site_data_dir: Path = SITE_DATA_DIR, today: date | None = None) -> None:
    today = today or today_pacific()
    venues = read_json(site_data_dir / "venues.json", [])
    screenings = build_screenings(_load_files(data_dir / "sources", "screenings"), [v["id"] for v in venues], today)
    all_posts = _load_files(data_dir / "posts", "posts")
    posts = build_posts(all_posts, today)
    features = build_features(all_posts)
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
