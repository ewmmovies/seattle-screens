"""Helpers shared by the posts scrapers."""
from __future__ import annotations

from datetime import datetime

from ..util import clean_ws


def parse_long_date(text: str | None) -> str | None:
    """'October 8, 2026' -> '2026-10-08'; anything unreadable -> None."""
    text = clean_ws(text)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None
