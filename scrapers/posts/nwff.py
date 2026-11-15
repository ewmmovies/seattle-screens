"""NWFF news (SPEC.md 5.8): https://nwfilmforum.org/news/, first page only.

Each entry is article.news-item: title link, a <datetime> line ("October 8, 2026")
and an excerpt. The site's RSS feed is stale and is not used.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..context import Context
from ..models import Post
from ..util import clean_ws, summarize
from ._common import parse_long_date

SOURCE_ID = "nwff"
SOURCE_NAME = "Northwest Film Forum"
NEWS_URL = "https://nwfilmforum.org/news/"


class ParseError(RuntimeError):
    """The page did not look the way this scraper expects."""


def parse_news(html: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("article.news-item")
    if not items:
        raise ParseError("no news items found; page layout may have changed")
    posts = []
    for item in items:
        heading = item.select_one("h1, h2, h3")
        link = heading.find_parent("a") if heading else None
        link = link or item.select_one("a[href]")
        if heading is None or link is None or not link.get("href"):
            raise ParseError("news item without a title link")
        excerpt = item.select_one(".text-editor")
        stamp = item.find("datetime")
        posts.append(Post(
            source=SOURCE_ID,
            source_name=SOURCE_NAME,
            title=clean_ws(heading.get_text()),
            url=link["href"],
            published=parse_long_date(stamp.get_text() if stamp else None),
            category="News",
            summary=summarize(excerpt.get_text(" ") if excerpt else ""),
        ))
    return posts


def fetch(ctx: Context) -> list[Post]:
    html = ctx.http.get_text(NEWS_URL)
    ctx.save_fixture("nwff_news.html", html)
    return parse_news(html)
