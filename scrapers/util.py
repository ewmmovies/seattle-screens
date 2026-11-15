"""Small helpers shared by scrapers: text cleaning, dates and times."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")

_TIME_12H_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*$", re.IGNORECASE)


def today_pacific() -> date:
    return datetime.now(PACIFIC).date()


def now_pacific_iso() -> str:
    """'2026-11-14T18:17:04-08:00': the timestamp format used in every data file."""
    return datetime.now(PACIFIC).replace(microsecond=0).isoformat()


def clean_ws(text: str | None) -> str:
    """Collapse runs of whitespace (including non-breaking spaces) to one space."""
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def slugify(text: str) -> str:
    """'My Night at Maud’s' -> 'my-night-at-mauds'. Non-Latin text is kept."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"['’‘`]", "", text.lower())
    text = re.sub(r"[^\w]+", "-", text, flags=re.UNICODE).strip("-_")
    return text or "untitled"


def match_key(text: str) -> str:
    """Loose form of a title for comparing two spellings of the same thing."""
    return re.sub(r"[\W_]+", "", slugify(text))


def parse_time_12h(text: str) -> str:
    """'3:45 PM' -> '15:45'; '7pm' -> '19:00'. Raises ValueError if unreadable."""
    match = _TIME_12H_RE.match(text)
    if not match:
        raise ValueError(f"unreadable time {text!r}")
    hour, minute, half = int(match.group(1)), int(match.group(2) or 0), match.group(3).lower()
    if not 1 <= hour <= 12 or minute > 59:
        raise ValueError(f"unreadable time {text!r}")
    hour = hour % 12 + (12 if half == "p" else 0)
    return f"{hour:02d}:{minute:02d}"


def epoch_ms_to_pacific(epoch_ms: int) -> datetime:
    return datetime.fromtimestamp(epoch_ms / 1000, PACIFIC)


def summarize(text: str | None, limit: int = 240) -> str:
    """Plain-text excerpt of at most `limit` characters, cut at a word boundary."""
    text = clean_ws(text)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return cut + "…"
