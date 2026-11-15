"""Build tests (SPEC.md section 10). Offline."""
import json
from datetime import date

from scrapers import build

TODAY = date(2026, 11, 17)
VENUES = [{"id": "siff-uptown"}, {"id": "nwff"}, {"id": "regal-meridian"}]


def rec(venue, day, title, time):
    return {"id": f"{venue}|{day}|{title.lower()}", "venue_id": venue, "date": day, "title": title,
            "showtimes": [{"time": time, "ticket_url": None, "note": None, "sold_out": False}]}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def setup(tmp_path):
    data, site = tmp_path / "data", tmp_path / "docs" / "data"
    write(site / "venues.json", VENUES)
    # nwff failed its last run: its file is stale but must still be used.
    write(data / "sources" / "nwff.json", {"source": "nwff", "scraped_at": "2026-11-15T06:00:00-08:00", "screenings": [
        rec("nwff", "2026-11-17", "Love Streams", "19:00"),
        rec("nwff", "2026-11-09", "Too Old", "19:00"),
    ]})
    write(data / "sources" / "siff.json", {"source": "siff", "scraped_at": "2026-11-17T06:00:00-08:00", "screenings": [
        rec("siff-uptown", "2026-11-17", "Paper Tiger", "21:00"),
        rec("siff-uptown", "2026-11-17", "Early Show", "13:00"),
        rec("siff-uptown", "2026-11-10", "Last Week", "19:00"),
        rec("siff-uptown", "2026-12-05", "Later", "19:00"),
    ]})
    write(data / "status.json", {"sources": {"nwff": {"ok": False, "error": "boom"}, "siff": {"ok": True}}})
    return data, site


def test_stale_and_fresh_sources_both_appear_and_old_records_drop(tmp_path):
    data, site = setup(tmp_path)
    build.build(data, site, TODAY)
    out = json.loads((site / "screenings.json").read_text())
    titles = [r["title"] for r in out["screenings"]]
    assert "Love Streams" in titles and "Paper Tiger" in titles
    assert "Too Old" not in titles  # 8 days before today
    assert "Last Week" in titles  # 7 days before today: kept
    assert out["range"] == {"start": "2026-11-10", "end": "2026-12-05"}


def test_sorted_by_date_then_venue_order_then_first_showtime(tmp_path):
    data, site = setup(tmp_path)
    build.build(data, site, TODAY)
    out = json.loads((site / "screenings.json").read_text())
    day = [r["title"] for r in out["screenings"] if r["date"] == "2026-11-17"]
    assert day == ["Early Show", "Paper Tiger", "Love Streams"]  # siff-uptown is listed before nwff


def test_status_is_copied_and_posts_written(tmp_path):
    data, site = setup(tmp_path)
    write(data / "posts" / "siff.json", {"posts": [
        {"id": "siff|/a", "title": "A", "published": "2026-10-01", "first_seen": "2026-10-02T00:00:00-07:00"},
        {"id": "siff|/b", "title": "B", "published": None, "first_seen": "2026-11-01T00:00:00-07:00"},
    ]})
    build.build(data, site, TODAY)
    status = json.loads((site / "status.json").read_text())
    assert status["sources"]["nwff"] == {"ok": False, "error": "boom"}
    assert "generated_at" in status
    posts = json.loads((site / "posts.json").read_text())["posts"]
    assert [p["title"] for p in posts] == ["A"]  # B has no date, so it is not listed


def test_missing_files_do_not_fail_the_build(tmp_path):
    site = tmp_path / "docs" / "data"
    build.build(tmp_path / "nothing", site, TODAY)
    out = json.loads((site / "screenings.json").read_text())
    assert out["screenings"] == [] and out["range"] == {"start": "2026-11-17", "end": "2026-11-17"}
    assert json.loads((site / "posts.json").read_text())["posts"] == []


def test_duplicate_ids_across_files_are_merged(tmp_path):
    data, site = setup(tmp_path)
    write(data / "sources" / "extra.json", {"screenings": [rec("siff-uptown", "2026-11-17", "Paper Tiger", "16:00")]})
    build.build(data, site, TODAY)
    out = json.loads((site / "screenings.json").read_text())
    tiger = [r for r in out["screenings"] if r["title"] == "Paper Tiger"]
    assert len(tiger) == 1 and [s["time"] for s in tiger[0]["showtimes"]] == ["16:00", "21:00"]
