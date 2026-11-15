/* News page (was Posts; reworked 2026-11-15).
   1. Happening Now: the same items as the rotating block on Listings (data/features.json).
   2. Latest News: dated posts from the last six months, newest first (data/posts.json). */
"use strict";

(() => {
  const { el } = SS;
  const happening = document.getElementById("happening");
  const latest = document.getElementById("posts");
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /** "2026-10-08" -> "Oct 8, 2026" (shown upper case by the stylesheet). */
  function shortDate(iso) {
    if (!SS.isISODate(iso)) return null;
    const [y, m, d] = iso.split("-").map(Number);
    return `${MONTHS[m - 1]} ${d}, ${y}`;
  }

  function cell(label, title, url, date, text) {
    const safe = SS.safeUrl(url);
    return el("li", { className: "cell" },
      el("div", { className: "cell-body" },
        el("p", { className: "small post-source" }, label),
        el("h3", { className: "title serif" }, safe ? SS.externalLink(safe, title) : title),
        date ? el("p", { className: "small post-date" }, date) : null,
        text ? el("p", { className: "post-summary" }, text) : null));
  }

  function happeningCell(item) {
    return cell([item.venue, item.kind].filter(Boolean).join(" · "), item.title, item.url,
      item.when, item.byline || item.description);
  }

  function postCell(post) {
    return cell([post.source_name || post.source, post.category].filter(Boolean).join(" · "),
      post.title, post.url, post.date_label || shortDate(post.published), post.summary);
  }

  async function show(container, path, pick, toCell, empty, failed) {
    try {
      const items = pick(await SS.loadJSON(path)).filter((x) => x && x.title);
      if (!items.length) SS.showMessage(container, empty);
      else container.replaceChildren(el("ul", { className: "grid post-grid" }, items.map(toCell)));
    } catch (error) {
      SS.showMessage(container, failed);
      console.error(error);
    }
  }

  show(happening, "data/features.json", (d) => [...(d.lead || []), ...(d.row || [])], happeningCell,
    "Nothing listed right now.", "Happening Now could not be loaded.");
  show(latest, "data/posts.json", (d) => d.posts || [], postCell,
    "No news in the last six months.", "News could not be loaded.");
})();
