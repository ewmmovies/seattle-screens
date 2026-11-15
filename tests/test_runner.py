"""Runner tests with fake sources (SPEC.md section 10). Offline."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import requests

from scrapers import run
from scrapers.http import decoded
from scrapers.context import Context
from scrapers.models import Post, Screening, Showtime
from scrapers.sources import siff

TODAY = date(2026, 11, 17)
VENUES = {"v-healthy", "v-raises", "v-invalid", "v-empty", "siff-uptown", "siff-downtown", "siff-film-center"}


def screening(venue, day="2026-11-17", title="A Film", time="19:00"):
    return Screening(venue_id=venue, date=day, title=title, showtimes=[Showtime(time=time)])


def fake(source_id, fetch):
    return SimpleNamespace(SOURCE_ID=source_id, VENUE_IDS=[f"v-{source_id}"], fetch=fetch)


def raises(ctx):
    raise ConnectionError("site down")


def invalid(ctx):
    return [screening("v-invalid", time="7pm")]  # time must be HH:MM


def empty(ctx):
    return [screening("v-empty", day="2026-11-10")]  # only a past date


def healthy(ctx):
    return [
        screening("v-healthy", title="New Film"),
        screening("v-healthy", title="New Film", time="21:00"),  # same id: merged
    ]


OLD_FILE = {"source": "x", "scraped_at": "old", "screenings": [{"id": "old"}]}


def seed(data_dir: Path, source_id: str):
    path = data_dir / "sources" / f"{source_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(OLD_FILE))
    return path


def test_one_bad_source_does_not_stop_the_others(tmp_path):
    files = {sid: seed(tmp_path, sid) for sid in ("raises", "invalid", "empty", "healthy")}
    sources = [fake("raises", raises), fake("invalid", invalid), fake("empty", empty), fake("healthy", healthy)]

    code = run.run(sources=sources, post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)

    assert code == 0
    for sid in ("raises", "invalid", "empty"):
        assert json.loads(files[sid].read_text()) == OLD_FILE, f"{sid} file should be untouched"
    written = json.loads(files["healthy"].read_text())
    assert [r["title"] for r in written["screenings"]] == ["New Film"]
    assert [s["time"] for s in written["screenings"][0]["showtimes"]] == ["19:00", "21:00"]

    status = json.loads((tmp_path / "status.json").read_text())["sources"]
    assert status["healthy"]["ok"] is True and status["healthy"]["count"] == 1
    assert status["healthy"]["last_success"] == status["healthy"]["last_attempt"]
    assert status["healthy"]["venue_ids"] == ["v-healthy"]
    assert status["raises"]["ok"] is False and "site down" in status["raises"]["error"]
    assert status["invalid"]["ok"] is False and "bad showtime" in status["invalid"]["error"]
    assert status["empty"]["ok"] is False and "empty result" in status["empty"]["error"]
    assert status["raises"]["last_success"] is None


def test_failure_keeps_the_previous_last_success(tmp_path):
    run.run(sources=[fake("healthy", healthy)], post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)
    first = json.loads((tmp_path / "status.json").read_text())["sources"]["healthy"]["last_success"]
    broken = fake("healthy", raises)
    run.run(sources=[broken], post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)
    entry = json.loads((tmp_path / "status.json").read_text())["sources"]["healthy"]
    assert entry["ok"] is False and entry["last_success"] == first and entry["count"] == 1


def test_exit_code_is_1_only_when_everything_failed(tmp_path):
    assert run.run(sources=[fake("raises", raises)], post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY) == 1
    assert run.run(sources=[], post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY) == 0


def test_status_for_sources_not_run_is_kept(tmp_path):
    (tmp_path / "status.json").write_text(json.dumps({"sources": {"regal": {"ok": True, "last_success": "x"}}}))
    run.run(sources=[fake("healthy", healthy)], post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["sources"]["regal"] == {"ok": True, "last_success": "x"}


def test_venue_ids_must_exist_in_venues_json(tmp_path):
    code = run.run(sources=[fake("healthy", healthy)], post_sources=[], data_dir=tmp_path, venue_ids={"other"}, today=TODAY)
    assert code == 1


def test_merge_keeps_recent_past_days_and_replaces_the_future():
    stored = [
        {"id": "a|2026-11-09|old", "date": "2026-11-09", "venue_id": "a", "title": "Too old", "showtimes": [{"time": "10:00"}]},
        {"id": "a|2026-11-12|past", "date": "2026-11-12", "venue_id": "a", "title": "Past", "showtimes": [{"time": "10:00"}]},
        {"id": "a|2026-11-18|gone", "date": "2026-11-18", "venue_id": "a", "title": "Cancelled", "showtimes": [{"time": "10:00"}]},
    ]
    new = [{"id": "a|2026-11-17|new", "date": "2026-11-17", "venue_id": "a", "title": "New", "showtimes": [{"time": "10:00"}]}]
    merged = run.merge_with_stored(new, stored, TODAY)
    assert [r["title"] for r in merged] == ["Past", "New"]


def test_cache_is_saved_per_source(tmp_path):
    def caches(ctx: Context):
        ctx.cache["https://example.org/film"] = {"fetched": "2026-11-17", "year": 1984}
        return healthy(ctx)

    run.run(sources=[fake("healthy", caches)], post_sources=[], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)
    cache = json.loads((tmp_path / "cache" / "healthy.json").read_text())
    assert cache["https://example.org/film"]["year"] == 1984


def test_posts_are_merged_by_id_and_keep_first_seen(tmp_path):
    def posts_v1(ctx):
        return [Post(source="nwff", source_name="NWFF", title="One", url="https://nwfilmforum.org/news/one/", published="2026-10-01")]

    def posts_v2(ctx):
        return [Post(source="nwff", source_name="NWFF", title="Two", url="https://nwfilmforum.org/news/two/", published="2026-11-01")]

    module = SimpleNamespace(SOURCE_ID="nwff", fetch=posts_v1)
    run.run(sources=[], post_sources=[module], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)
    first_seen = json.loads((tmp_path / "posts" / "nwff.json").read_text())["posts"][0]["first_seen"]
    module.fetch = posts_v2
    run.run(sources=[], post_sources=[module], data_dir=tmp_path, venue_ids=VENUES, today=TODAY)
    posts = json.loads((tmp_path / "posts" / "nwff.json").read_text())["posts"]
    assert [p["title"] for p in posts] == ["Two", "One"]
    assert posts[1]["first_seen"] == first_seen
    assert posts[0]["id"] == "nwff|/news/two/"


# --- the real SIFF scraper inside the runner, network replaced by fixtures ---------


def _heading(d: date) -> str:
    return f"{d:%A, %B} {d.day}, {d.year}"


class FixtureHttp:
    """Serves the saved SIFF pages instead of going online."""

    request_count = 0

    def __init__(self):
        folder = Path(__file__).parent / "fixtures" / "siff"
        self.pages = {
            "2026-11-17": (folder / "calendar_2026-11-17.html").read_text(encoding="utf-8"),
            "empty": (folder / "calendar_2027-03-02_empty.html").read_text(encoding="utf-8"),
        }

    def get_text(self, url, **kwargs):
        self.request_count += 1
        day = url.rsplit("date=", 1)[1]
        if day == "2026-11-17":
            return self.pages["2026-11-17"]
        # Reuse the empty page, with its date heading rewritten to the day asked for.
        return self.pages["empty"].replace("Tuesday, March 2, 2027", _heading(date.fromisoformat(day)))


def test_siff_runs_inside_the_runner(tmp_path):
    venues = json.loads((Path(__file__).parent.parent / "docs" / "data" / "venues.json").read_text())
    code = run.run(
        sources=[siff], post_sources=[], data_dir=tmp_path,
        venue_ids={v["id"] for v in venues}, today=TODAY, http=FixtureHttp(),
    )
    assert code == 0
    written = json.loads((tmp_path / "sources" / "siff.json").read_text())
    # Six film-venue-day records, the same count test_siff.py gets on its own.
    assert len(written["screenings"]) == len(siff.build_screenings(
        siff.parse_day(FixtureHttp().pages["2026-11-17"], TODAY))) == 6
    status = json.loads((tmp_path / "status.json").read_text())["sources"]["siff"]
    assert status["ok"] is True and status["count"] == 6


def resp(body, ctype):
    r = requests.Response(); r._content = body; r.headers["content-type"] = ctype; r.encoding = None
    return r


def test_utf8_without_charset_is_read_as_utf8():
    assert decoded(resp("it’s".encode(), "text/html")) == "it’s"
    assert decoded(resp("café".encode("latin-1"), "text/html; charset=ISO-8859-1")) == "café"
