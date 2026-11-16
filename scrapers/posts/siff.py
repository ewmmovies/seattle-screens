"""SIFF blog and press releases (SPEC.md 5.8), first page of each.

- https://www.siff.net/media/blog: div.item with a category label, title, date and excerpt.
- https://www.siff.net/media/news-x39250: press releases with title and excerpt but no
  date on the index page. Each release's own page prints its date under the title
  ("9/22/2026", usually followed by a press contact), so that page is read once and
  remembered; dates do not change. A page with no readable date is tried again after
  a week, and until then the post sorts by the date it was first seen.
"""
from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup

from ..context import Context
from ..models import Post
from ..util import clean_ws, summarize
from ._common import parse_long_date

SOURCE_ID = "siff"
SOURCE_NAME = "SIFF"
BASE_URL = "https://www.siff.net"
BLOG_URL = BASE_URL + "/media/blog"
NEWS_URL = BASE_URL + "/media/news-x39250"


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


def _items(html: str, path: str):
    soup = BeautifulSoup(html, "html.parser")
    items = [i for i in soup.select("div.item") if i.select_one(f'h3 a[href^="{path}"]')]
    if not items:
        raise ParseError(f"no {path} entries found; page layout may have changed")
    return items


def _excerpt(item) -> str:
    texts = [clean_ws(p.get_text(" ")) for p in item.select("p")
             if "button-group" not in (p.get("class") or []) and "img-wrap" not in (p.get("class") or [])
             and not p.find_parent(class_="img-wrap") and "h5" not in (p.get("class") or [])]
    return summarize(" ".join(t for t in texts if t))


def parse_blog(html: str) -> list[Post]:
    posts = []
    for item in _items(html, "/media/blog/"):
        link = item.select_one('h3 a[href^="/media/blog/"]')
        label = item.select_one("p.h5")
        date_node = item.select_one("h4")
        posts.append(Post(
            source=SOURCE_ID,
            source_name=SOURCE_NAME,
            title=clean_ws(link.get_text()),
            url=BASE_URL + link["href"],
            published=parse_long_date(date_node.get_text() if date_node else None),
            category=clean_ws(label.get_text()) if label else "Blog",
            summary=_excerpt(item),
        ))
    return posts


def parse_news(html: str) -> list[Post]:
    posts = []
    for item in _items(html, "/media/news/"):
        link = item.select_one('h3 a[href^="/media/news/"]')
        posts.append(Post(
            source=SOURCE_ID,
            source_name=SOURCE_NAME,
            title=clean_ws(link.get_text()),
            url=BASE_URL + link["href"],
            published=None,
            category="Press release",
            summary=_excerpt(item),
        ))
    return posts


_SLASH_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\b")  # contact details often follow the date


def parse_release_date(html: str) -> str | None:
    """Press release page -> 'YYYY-MM-DD' from the 'p.small' date line, or None."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("p.small"):
        match = _SLASH_DATE_RE.match(clean_ws(node.get_text()))
        if match:
            month, day, year = (int(g) for g in match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def fetch(ctx: Context) -> list[Post]:
    blog = ctx.http.get_text(BLOG_URL)
    ctx.save_fixture("siff_blog.html", blog)
    news = ctx.http.get_text(NEWS_URL)
    ctx.save_fixture("siff_news.html", news)
    releases = parse_news(news)
    for post in releases:
        def load(url=post.url):
            try:
                return parse_release_date(ctx.http.get_text(url))
            except requests.HTTPError as error:  # a missing page only costs the date
                print(f"[posts/siff] release page skipped: {error}", file=sys.stderr)
                return None
        key = "release2:" + post.url  # "2": earlier runs remembered dates they could not read
        ctx.cache.pop(post.url, None)
        post.published = ctx.cached(key, load, max_age_days=3650)
        if post.published is None:  # do not remember a missing date for long
            post.published = ctx.cached(key, load, max_age_days=7)
    return parse_blog(blog) + releases
