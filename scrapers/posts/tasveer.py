"""Tasveer's own blog, from its WordPress feed: https://tasveer.org/feed/.

Blog only (decided with Elijah 2026-11-15); the Press page, which links to outside
coverage, is not used. When this was built the newest post was from June 2025, so
nothing shows until Tasveer posts again; the six-month rule is applied by the build.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..context import Context
from ..models import Post
from ..util import PACIFIC, clean_ws, summarize

SOURCE_ID = "tasveer"
SOURCE_NAME = "Tasveer"
FEED_URL = "https://tasveer.org/feed/"


class ParseError(RuntimeError):
    """The feed did not look the way this scraper expects."""


def parse_feed(xml_text: str) -> list[Post]:
    try:
        root = ET.fromstring(xml_text.lstrip())
    except ET.ParseError as error:
        raise ParseError(f"feed is not valid XML: {error}") from error
    items = root.findall("./channel/item")
    if root.find("./channel") is None:
        raise ParseError("not an RSS feed")
    posts = []
    for item in items:
        title = clean_ws(item.findtext("title"))
        link = clean_ws(item.findtext("link"))
        if not title or not link.startswith("http"):
            continue
        published = None
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(PACIFIC).date().isoformat()
        except (TypeError, ValueError):
            pass
        description = BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" ")
        categories = [clean_ws(c.text) for c in item.findall("category") if clean_ws(c.text)]
        posts.append(Post(
            source=SOURCE_ID,
            source_name=SOURCE_NAME,
            title=title,
            url=link,
            published=published,
            category=categories[0] if categories else "Blog",
            summary=summarize(description),
        ))
    return posts


def fetch(ctx: Context) -> list[Post]:
    text = ctx.http.get_text(FEED_URL)
    ctx.save_fixture("tasveer_feed.xml", text)
    return parse_feed(text)
