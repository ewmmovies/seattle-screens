"""What the runner hands to each scraper's fetch() (SPEC.md section 4.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable
from pathlib import Path

from .http import Http
from .util import today_pacific

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Context:
    http: Http = field(default_factory=Http)
    today: date = field(default_factory=today_pacific)
    horizon_days: int = 21
    cache: dict = field(default_factory=dict)  # persisted by the runner per source
    fixtures_dir: Path | None = None  # set by --save-fixtures

    def save_fixture(self, name: str, text: str) -> None:
        """Keep a copy of a real response for offline tests. No-op unless enabled."""
        if self.fixtures_dir is None:
            return
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        (self.fixtures_dir / name).write_text(text, encoding="utf-8")

    def cached(self, key: str, loader: Callable[[], object], max_age_days: int = 7):
        """Detail-page cache (SPEC.md 4.4): reuse what was fetched in the last week."""
        entry = self.cache.get(key)
        if entry:
            try:
                age = (self.today - date.fromisoformat(entry["fetched"])).days
            except (KeyError, TypeError, ValueError):
                age = max_age_days
            if age < max_age_days:
                return entry["data"]
        data = loader()
        self.cache[key] = {"fetched": self.today.isoformat(), "data": data}
        return data
