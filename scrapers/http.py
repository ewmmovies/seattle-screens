"""Shared HTTP client (SPEC.md section 4.4).

One instance is shared by all scrapers in a run. It identifies the project
honestly, waits between requests to the same site, and retries only on
network errors and server (5xx) errors.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

import requests

REPO_URL = "https://github.com/ewmmovies/seattle-screens"
USER_AGENT = f"SeattleScreens/1.0 (personal listings project; +{REPO_URL})"


class Http:
    def __init__(
        self,
        user_agent: str = USER_AGENT,
        timeout: float = 30,
        retries: int = 2,
        min_delay: float = 1.0,
    ) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.timeout = timeout
        self.retries = retries
        self.min_delay = min_delay
        self.request_count = 0
        self._last_request: dict[str, float] = {}

    def _wait_turn(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.min_delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request[host] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(2 * attempt)
            self._wait_turn(url)
            self.request_count += 1
            try:
                response = self.session.request(method, url, **kwargs)
            except requests.RequestException as error:  # network trouble: retry
                last_error = error
                continue
            if response.status_code >= 500:  # server trouble: retry
                last_error = requests.HTTPError(f"{response.status_code} for {url}")
                continue
            response.raise_for_status()  # 4xx: fail now, retrying will not help
            return response
        raise last_error  # type: ignore[misc]

    def get_text(self, url: str, **kwargs) -> str:
        return self.request("GET", url, **kwargs).text

    def get_json(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs).json()

    def post_text(self, url: str, **kwargs) -> str:
        return self.request("POST", url, **kwargs).text
