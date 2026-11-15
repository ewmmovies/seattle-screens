"""What the runner hands to each scraper's fetch() (SPEC.md section 4.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
