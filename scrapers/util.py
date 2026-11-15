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


_SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "nor", "of",
                "on", "or", "the", "to", "vs", "vs.", "via", "with"}
_ROMAN_RE = re.compile(r"^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$", re.IGNORECASE)


def title_case_if_all_caps(text: str) -> str:
    """'WILL SUCCESS SPOIL ROCK HUNTER?' -> 'Will Success Spoil Rock Hunter?'.

    Text that already has any lower-case letter is returned unchanged (SPEC.md 3.2:
    keep the venue's capitalization unless it is ALL CAPS). Roman numerals stay upper case.
    """
    if not any(ch.isalpha() for ch in text) or any(ch.islower() for ch in text):
        return text
    words = text.split(" ")
    out: list[str] = []
    after_break = True  # start of title, or after ':' '–' '-' '.' etc.
    for word in words:
        bare = word.strip("\"'“”‘’()[]!?,.:;")
        if bare and _ROMAN_RE.match(bare) and len(bare) > 1:
            fixed = word.upper()
        elif not after_break and bare.lower() in _SMALL_WORDS:
            fixed = word.lower()
        else:
            # Capitalise the first letter of each hyphen-joined part: SPIDER-MAN -> Spider-Man.
            fixed = "-".join(re.sub(r"^([^A-Za-zÀ-ÿ]*)([A-Za-zÀ-ÿ])", lambda m: m.group(1) + m.group(2).upper(), part.lower())
                             for part in word.split("-"))
        out.append(fixed)
        after_break = bool(word) and (word[-1] in ":.!?–—" or word in {"-", "–", "—", "+"})
    return " ".join(out)


def parse_iso_duration_minutes(text: str | None) -> int | None:
    """'PT1H56M' -> 116; 'PT99M' -> 99; anything else -> None."""
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", (text or "").strip())
    if not match or not (match.group(1) or match.group(2)):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def parse_hm_minutes(text: str | None) -> int | None:
    """'2h 20m' -> 140; '88 min' -> 88; '116 minutes' -> 116."""
    text = clean_ws(text).lower()
    match = re.fullmatch(r"(?:(\d+)\s*h(?:ours?|r\.?)?)?\s*(?:(\d+)\s*m(?:in(?:utes?|\.)?)?)?", text)
    if not match or not (match.group(1) or match.group(2)):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
