"""Data model shared by every scraper (SPEC.md section 3.2).

Scrapers build Screening objects; the runner calls validate() on each one
before anything is written to disk.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .util import slugify

FORMATS = {"35mm", "70mm", "16mm", "DCP", "Digital", "Film"}
KINDS = {"film", "event"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_URL_RE = re.compile(r"^https?://")


class ValidationError(ValueError):
    """A record does not match the data model."""


@dataclass
class Showtime:
    time: str  # "HH:MM", 24-hour, Pacific time
    ticket_url: str | None = None
    note: str | None = None
    sold_out: bool = False


@dataclass
class Screening:
    venue_id: str
    date: str  # "YYYY-MM-DD", the date the venue lists the show under
    title: str
    showtimes: list[Showtime]
    kind: str = "film"
    series: str | None = None
    directors: list[str] = field(default_factory=list)
    year: int | None = None
    runtime_min: int | None = None
    format: str | None = None
    notes: list[str] = field(default_factory=list)
    url: str | None = None

    @property
    def id(self) -> str:
        return f"{self.venue_id}|{self.date}|{slugify(self.title)}"

    def to_dict(self) -> dict:
        data = asdict(self)
        return {"id": self.id, **data}

    def validate(self, venue_ids: set[str] | None = None) -> None:
        """Raise ValidationError if this record breaks the data model."""

        def fail(message: str) -> None:
            raise ValidationError(f"{self.venue_id} {self.date} {self.title!r}: {message}")

        if venue_ids is not None and self.venue_id not in venue_ids:
            fail(f"unknown venue_id {self.venue_id!r}")
        if not _DATE_RE.match(self.date):
            fail(f"bad date {self.date!r}")
        if not self.title or self.title != self.title.strip():
            fail("title is empty or has stray whitespace")
        if self.kind not in KINDS:
            fail(f"bad kind {self.kind!r}")
        if self.format is not None and self.format not in FORMATS:
            fail(f"bad format {self.format!r}")
        if self.year is not None and not 1880 <= self.year <= 2100:
            fail(f"implausible year {self.year!r}")
        if self.runtime_min is not None and not 1 <= self.runtime_min <= 900:
            fail(f"implausible runtime {self.runtime_min!r}")
        if not self.showtimes:
            fail("no showtimes")
        for note in self.notes:
            if not note or len(note) > 200:
                fail("note is empty or longer than 200 characters")
        for show in self.showtimes:
            if not _TIME_RE.match(show.time):
                fail(f"bad showtime {show.time!r}")
            if show.note is not None and (not show.note or len(show.note) > 200):
                fail("showtime note is empty or longer than 200 characters")
        times = [show.time for show in self.showtimes]
        if times != sorted(times):
            fail("showtimes are not sorted")


def merge_screenings(records: list[Screening]) -> list[Screening]:
    """Combine records that share an id (same venue, date and title).

    Showtimes are unioned and re-sorted; the first record's other fields win,
    with gaps filled from later ones.
    """
    merged: dict[str, Screening] = {}
    for record in records:
        existing = merged.get(record.id)
        if existing is None:
            merged[record.id] = record
            continue
        seen = {show.time for show in existing.showtimes}
        existing.showtimes.extend(s for s in record.showtimes if s.time not in seen)
        existing.showtimes.sort(key=lambda s: s.time)
        for note in record.notes:
            if note not in existing.notes:
                existing.notes.append(note)
        for name in ("series", "year", "runtime_min", "format", "url"):
            if getattr(existing, name) is None:
                setattr(existing, name, getattr(record, name))
        if not existing.directors:
            existing.directors = record.directors
    return list(merged.values())


@dataclass
class Post:
    """One item in the news feed (SPEC.md section 3.3)."""

    source: str
    source_name: str
    title: str
    url: str
    published: str | None = None  # "YYYY-MM-DD", or None when the source gives no date
    category: str | None = None
    summary: str = ""
    first_seen: str | None = None  # set by the runner the first time it sees the post

    @property
    def id(self) -> str:
        path = re.sub(r"^https?://[^/]+", "", self.url) or "/"
        return f"{self.source}|{path}"

    def to_dict(self) -> dict:
        return {"id": self.id, **asdict(self)}

    def validate(self) -> None:
        def fail(message: str) -> None:
            raise ValidationError(f"post {self.source} {self.title!r}: {message}")

        if not self.title or self.title != self.title.strip():
            fail("title is empty or has stray whitespace")
        if not _URL_RE.match(self.url or ""):
            fail(f"bad url {self.url!r}")
        if self.published is not None and not _DATE_RE.match(self.published):
            fail(f"bad published date {self.published!r}")
        if len(self.summary) > 240:
            fail("summary longer than 240 characters")
