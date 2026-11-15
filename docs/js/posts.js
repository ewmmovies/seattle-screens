/* Posts page (SPEC.md section 7.5): combined NWFF and SIFF feed, newest first. No images. */
"use strict";

(() => {
  const { el } = SS;
  const content = document.getElementById("posts");
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /** "2026-10-08" -> "Oct 8, 2026" (shown upper case by the stylesheet). */
  function shortDate(iso) {
    if (!SS.isISODate(iso)) return null;
    const [y, m, d] = iso.split("-").map(Number);
    return `${MONTHS[m - 1]} ${d}, ${y}`;
  }

  function cell(post) {
    const url = SS.safeUrl(post.url);
    const date = shortDate(post.published);
    return el("li", { className: "cell" },
      el("div", { className: "cell-body" },
        el("p", { className: "small post-source" }, post.source_name || post.source),
        el("h3", { className: "title serif" }, url ? SS.externalLink(url, post.title) : post.title),
        date ? el("p", { className: "small post-date" }, date) : null,
        post.summary ? el("p", { className: "post-summary" }, post.summary) : null));
  }

  async function init() {
    try {
      const data = await SS.loadJSON("data/posts.json");
      const posts = (data.posts || []).filter((p) => p && p.title);
      if (!posts.length) {
        SS.showMessage(content, "No posts yet.");
        return;
      }
      content.replaceChildren(el("ul", { className: "grid post-grid" }, posts.map(cell)));
    } catch (error) {
      SS.showMessage(content, "Posts could not be loaded.");
      console.error(error);
    }
  }

  init();
})();
