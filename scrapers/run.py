"""Runner: fetch every source, keep the last good data, record status.

    python -m scrapers.run                     every source, then posts
    python -m scrapers.run --source siff       one source (repeatable)
    python -m scrapers.run --save-fixtures     also save real responses for tests
    python -m scrapers.run --posts-only / --no-posts

Rules (SPEC.md section 4.2):
  - Each source runs on its own. One failing never stops the others.
  - Any invalid record, or nothing dated today or later, fails the whole source.
  - A failed source keeps its previous data file untouched and is marked
    ok: false in data/status.json, so the site shows its venues as out of date.
  - Exit code is 0 unless every source attempted failed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

from .context import REPO_ROOT, Context
from .http import Http
from .models import Post, Screening, ValidationError, merge_screenings
from .util import now_pacific_iso, today_pacific

DATA_DIR = REPO_ROOT / "data"
VENUES_FILE = REPO_ROOT / "docs" / "data" / "venues.json"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

KEEP_PAST_DAYS = 7  # past screenings stay this long so "previous day" works
POSTS_PER_SOURCE = 40


class EmptyResult(RuntimeError):
    """A source returned nothing dated today or later."""


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data) -> None:
    """Write via a temporary file so a crash never leaves half a file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def known_venue_ids(venues_file: Path = VENUES_FILE) -> set[str]:
    return {venue["id"] for venue in read_json(venues_file, [])}


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------


def discover(package: str) -> list[ModuleType]:
    """Import every module in scrapers/sources or scrapers/posts."""
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError:
        return []
    modules = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        if hasattr(module, "SOURCE_ID") and hasattr(module, "fetch"):
            modules.append(module)
    return modules


# --------------------------------------------------------------------------
# One screening source
# --------------------------------------------------------------------------


def check_screenings(records, module: ModuleType, venue_ids: set[str], today: date) -> list[Screening]:
    """Validate a scraper's output. Raises on anything wrong."""
    if not isinstance(records, list):
        raise ValidationError(f"fetch() returned {type(records).__name__}, not a list")
    allowed = set(module.VENUE_IDS)
    unknown = allowed - venue_ids
    if venue_ids and unknown:
        raise ValidationError(f"VENUE_IDS not in venues.json: {sorted(unknown)}")
    for record in records:
        if not isinstance(record, Screening):
            raise ValidationError(f"fetch() returned a {type(record).__name__}, not a Screening")
        record.validate(allowed)
    records = merge_screenings(records)
    if not any(record.date >= today.isoformat() for record in records):
        raise EmptyResult("empty result: nothing dated today or later")
    return records


def merge_with_stored(new: list[dict], stored: list[dict], today: date) -> list[dict]:
    """New records replace everything from today on; recent past days are kept."""
    oldest = (today - timedelta(days=KEEP_PAST_DAYS)).isoformat()
    today_s = today.isoformat()
    new_ids = {record["id"] for record in new}
    kept = [
        record
        for record in stored
        if oldest <= record.get("date", "") < today_s and record.get("id") not in new_ids
    ]
    merged = kept + new
    merged.sort(key=lambda r: (r["date"], r["venue_id"], r["showtimes"][0]["time"] if r["showtimes"] else "", r["title"]))
    return merged


def run_source(
    module: ModuleType,
    *,
    http: Http,
    today: date,
    data_dir: Path,
    status: dict,
    venue_ids: set[str],
    fixtures_root: Path | None = None,
    horizon_days: int = 21,
) -> bool:
    source_id = module.SOURCE_ID
    entry = status.setdefault(source_id, {})
    entry["last_attempt"] = now_pacific_iso()
    entry["venue_ids"] = list(module.VENUE_IDS)
    entry.setdefault("last_success", None)
    entry.setdefault("count", 0)

    cache_file = data_dir / "cache" / f"{source_id}.json"
    ctx = Context(
        http=http,
        today=today,
        horizon_days=horizon_days,
        cache=read_json(cache_file, {}),
        fixtures_dir=(fixtures_root / source_id) if fixtures_root else None,
    )
    requests_before = http.request_count
    try:
        records = check_screenings(module.fetch(ctx), module, venue_ids, today)
    except Exception as error:  # noqa: BLE001 - one source must never stop the rest
        traceback.print_exc()
        entry["ok"] = False
        entry["error"] = f"{type(error).__name__}: {error}".splitlines()[0][:300]
        print(f"[{source_id}] FAILED: {entry['error']} (previous data kept)")
        return False
    finally:
        if ctx.cache:
            write_json(cache_file, ctx.cache)

    source_file = data_dir / "sources" / f"{source_id}.json"
    stored = read_json(source_file, {}).get("screenings", [])
    merged = merge_with_stored([record.to_dict() for record in records], stored, today)
    write_json(source_file, {"source": source_id, "scraped_at": entry["last_attempt"], "screenings": merged})
    entry.update(ok=True, error=None, last_success=entry["last_attempt"], count=len(records))
    print(f"[{source_id}] ok: {len(records)} screenings, {http.request_count - requests_before} requests")
    return True


# --------------------------------------------------------------------------
# One post source
# --------------------------------------------------------------------------


def merge_posts(new: list[Post], stored: list[dict], seen_at: str) -> list[dict]:
    """Keep stored posts, add new ones by id, cap at POSTS_PER_SOURCE (newest first)."""
    # Only today's fetch decides what is current or now playing.
    by_id = {post["id"]: {**post, "current": False, "now_playing": False} for post in stored}
    for post in new:
        data = post.to_dict()
        previous = by_id.get(data["id"])
        data["first_seen"] = (previous or {}).get("first_seen") or seen_at
        by_id[data["id"]] = data
    posts = sorted(by_id.values(), key=lambda p: (p.get("published") or p["first_seen"][:10]), reverse=True)
    return posts[:POSTS_PER_SOURCE]


def run_posts(module: ModuleType, *, http: Http, today: date, data_dir: Path, status: dict, fixtures_root: Path | None = None) -> bool:
    source_id = module.SOURCE_ID
    entry = status.setdefault(source_id, {})
    entry["last_attempt"] = now_pacific_iso()
    entry.setdefault("last_success", None)
    entry.setdefault("count", 0)
    cache_file = data_dir / "cache" / f"posts_{source_id}.json"
    ctx = Context(http=http, today=today, cache=read_json(cache_file, {}),
                  fixtures_dir=(fixtures_root / "posts") if fixtures_root else None)
    try:
        posts = module.fetch(ctx)
        if not posts:
            raise EmptyResult("empty result: no posts found")
        for post in posts:
            if not isinstance(post, Post):
                raise ValidationError(f"fetch() returned a {type(post).__name__}, not a Post")
            post.validate()
    except Exception as error:  # noqa: BLE001
        traceback.print_exc()
        entry["ok"] = False
        entry["error"] = f"{type(error).__name__}: {error}".splitlines()[0][:300]
        print(f"[posts/{source_id}] FAILED: {entry['error']} (previous posts kept)")
        return False
    finally:
        if ctx.cache:
            write_json(cache_file, ctx.cache)

    posts_file = data_dir / "posts" / f"{source_id}.json"
    stored = read_json(posts_file, {}).get("posts", [])
    merged = merge_posts(posts, stored, entry["last_attempt"])
    write_json(posts_file, {"source": source_id, "scraped_at": entry["last_attempt"], "posts": merged})
    entry.update(ok=True, error=None, last_success=entry["last_attempt"], count=len(posts))
    print(f"[posts/{source_id}] ok: {len(posts)} posts")
    return True


# --------------------------------------------------------------------------
# Whole run
# --------------------------------------------------------------------------


def run(
    *,
    sources: list[ModuleType],
    post_sources: list[ModuleType],
    data_dir: Path = DATA_DIR,
    venue_ids: set[str] | None = None,
    today: date | None = None,
    http: Http | None = None,
    fixtures_root: Path | None = None,
) -> int:
    """Run the given scrapers and return the process exit code."""
    today = today or today_pacific()
    http = http or Http()
    venue_ids = known_venue_ids() if venue_ids is None else venue_ids
    status_file = data_dir / "status.json"
    status = read_json(status_file, {})
    status.setdefault("sources", {})
    status.setdefault("posts", {})

    results = []
    for module in sources:
        results.append(
            run_source(module, http=http, today=today, data_dir=data_dir, status=status["sources"],
                       venue_ids=venue_ids, fixtures_root=fixtures_root)
        )
    for module in post_sources:
        results.append(
            run_posts(module, http=http, today=today, data_dir=data_dir, status=status["posts"],
                      fixtures_root=fixtures_root)
        )

    status["generated_at"] = now_pacific_iso()
    write_json(status_file, status)
    print(f"Done: {sum(results)} of {len(results)} succeeded, {http.request_count} requests in total.")
    if results and not any(results):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.run", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", default=[], metavar="ID", help="run only this source (repeatable)")
    parser.add_argument("--save-fixtures", action="store_true", help="save real responses to tests/fixtures/")
    parser.add_argument("--posts-only", action="store_true", help="run only the posts scrapers")
    parser.add_argument("--no-posts", action="store_true", help="skip the posts scrapers")
    args = parser.parse_args(argv)

    sources = [] if args.posts_only else discover("scrapers.sources")
    post_sources = [] if args.no_posts else discover("scrapers.posts")
    if args.source:
        wanted = set(args.source)
        found = {m.SOURCE_ID for m in sources} | {m.SOURCE_ID for m in post_sources}
        missing = wanted - found
        if missing:
            parser.error(f"unknown source(s): {', '.join(sorted(missing))}. Known: {', '.join(sorted(found)) or 'none'}")
        sources = [m for m in sources if m.SOURCE_ID in wanted]
        post_sources = [m for m in post_sources if m.SOURCE_ID in wanted]

    return run(sources=sources, post_sources=post_sources,
               fixtures_root=FIXTURES_DIR if args.save_fixtures else None)


if __name__ == "__main__":
    sys.exit(main())
